"""Single-script bird detection loop.

YOLO + optional sliced inference (the SAHI *technique*, via ``supervision``'s
``InferenceSlicer``) over offline video, producing an annotated video (boxes + a
picture-in-picture zoom inset) and a per-frame JSONL detections sidecar.

The sidecar is the tracker-ready handoff a future ByteTrack stage consumes — see the
PRD at ``.scratch/bird-detection-loop/PRD.md`` and the ADRs under ``docs/adr/``.

Run with:  ``uv run detect-birds --source clip.mp4 [--slice | --no-slice] ...``
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

import cv2
import numpy as np
import supervision as sv
from tqdm import tqdm
from ultralytics import YOLO


class _ByteTracker(Protocol):
    """The slice of ``sv.ByteTrack`` the loop depends on.

    ``sv.ByteTrack`` is a deprecation proxy (removed in supervision 0.30) that type
    checkers can't treat as a class, so we type against this structural interface instead.
    Runtime still constructs ``sv.ByteTrack`` per ADR-0006.
    """

    def update_with_detections(self, detections: sv.Detections) -> sv.Detections: ...


# --- defaults / constants (resolution-relative where it matters) -------------------
COCO_BIRD_CLASS_ID = 14
DEFAULT_WEIGHTS = "yolo11n.pt"
DEFAULT_CONF = 0.15  # recall-first; tracking is the false-positive filter (ADR-0004)
DEFAULT_SLICE_WH = (640, 640)
DEFAULT_OVERLAP_RATIO = (0.2, 0.2)
DEFAULT_THREAD_WORKERS = 4
DEFAULT_TRACK_BUFFER = 30  # lost_track_buffer: frames a lost id is held (ADR-0006)
DEFAULT_TRACK_ACTIVATION = 0.25  # min conf to start a track; sits above recall-first conf
DEFAULT_ZOOM_SIZE = 0.05  # crop side as a fraction of frame width
ZOOM_PANEL_FRACTION = 0.25  # inset panel side as a fraction of frame width
# effective magnification = ZOOM_PANEL_FRACTION / zoom_size (≈5x at defaults)
ZOOM_EMA_ALPHA = 0.3  # smoothing on the inset centre (lower = smoother)
ZOOM_BORDER_BGR = (0, 255, 0)
ZOOM_MIN_CROP_PX = 8  # floor on the crop side so tiny --zoom-size stays sampleable
ZOOM_LABEL_SCALE = 0.006  # identity-slot #id font scale per panel px (resolution-relative)
ZOOM_LABEL_MIN_SCALE = 0.4


@dataclass(frozen=True)
class DetectConfig:
    """Everything the per-frame detector needs, fixed for a run."""

    conf: float
    classes: tuple[int, ...] | None  # None = keep all classes
    device: str
    use_slicing: bool
    slice_wh: tuple[int, int]
    overlap_ratio_wh: tuple[float, float]
    overlap_filter: str  # "nms" | "nmm"
    thread_workers: int


@dataclass(frozen=True)
class RunPaths:
    source: Path
    output: Path
    sidecar: Path


@dataclass(frozen=True)
class TrackConfig:
    """In-loop ByteTrack settings for a run (ADR-0006)."""

    enabled: bool
    activation: float  # track_activation_threshold (min conf to start a track)
    buffer: int  # lost_track_buffer (frames a lost id and its zoom slot are held)


@dataclass(frozen=True)
class ZoomConfig:
    """Zoom Inset settings for a run (see CONTEXT.md: Zoom Inset / Zoom Panel)."""

    enabled: bool
    size: float  # crop side as a fraction of frame width
    max_panels: int  # confidence-mode: follow top-N; identity-mode: id-pinned slot count
    track_id: int | None = None  # identity-mode: lock the inset to one tracker_id


# --- device ------------------------------------------------------------------------
def resolve_device(requested: str | None) -> str:
    """Pick cuda -> mps -> cpu unless the user forced a device."""
    if requested and requested != "auto":
        return requested
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


# --- detection ---------------------------------------------------------------------
def _overlap_filter(name: str) -> sv.OverlapFilter:
    if name == "nmm":
        return sv.OverlapFilter.NON_MAX_MERGE
    return sv.OverlapFilter.NON_MAX_SUPPRESSION


def make_detector(model: YOLO, cfg: DetectConfig):
    """Return ``detect(frame) -> sv.Detections``, abstracting the slicing toggle.

    Both branches return ``sv.Detections`` so nothing downstream branches on slicing
    (ADR-0002/0003).
    """
    classes = list(cfg.classes) if cfg.classes else None

    def infer(image: np.ndarray) -> sv.Detections:
        result = model(
            image,
            conf=cfg.conf,
            classes=classes,
            device=cfg.device,
            verbose=False,
        )[0]
        return sv.Detections.from_ultralytics(result)

    if not cfg.use_slicing:
        return infer

    # supervision takes absolute overlap in px; we expose a resolution-relative ratio.
    overlap_wh = (
        int(cfg.overlap_ratio_wh[0] * cfg.slice_wh[0]),
        int(cfg.overlap_ratio_wh[1] * cfg.slice_wh[1]),
    )
    slicer = sv.InferenceSlicer(
        callback=infer,
        slice_wh=cfg.slice_wh,
        overlap_wh=overlap_wh,
        overlap_filter=_overlap_filter(cfg.overlap_filter),
        thread_workers=cfg.thread_workers,
    )
    return lambda frame: slicer(frame)


# --- sidecar -----------------------------------------------------------------------
def detection_records(
    detections: sv.Detections, track_map: dict[int, int] | None = None
) -> list[dict]:
    """Serialise detections to plain dicts (source-pixel xyxy).

    Every raw detection is emitted (ADR-0004). When ``track_map`` is given (``--track``),
    each row gains ``"track_id"`` — the int from the row's confirmed Track, or ``null`` for
    recall-first noise dropped by ByteTrack (ADR-0006). When ``None`` (``--no-track``) the
    key is omitted, leaving today's schema byte-for-byte unchanged.
    """
    if len(detections) == 0:
        return []
    names = detections.data.get("class_name") if detections.data else None
    records = []
    for i in range(len(detections)):
        x1, y1, x2, y2 = (round(float(v), 1) for v in detections.xyxy[i])
        conf = detections.confidence[i] if detections.confidence is not None else None
        cls = detections.class_id[i] if detections.class_id is not None else None
        record = {
            "xyxy": [x1, y1, x2, y2],
            "conf": round(float(conf), 4) if conf is not None else None,
            "cls": int(cls) if cls is not None else None,
            "name": str(names[i]) if names is not None else None,
        }
        if track_map is not None:
            tid = track_map.get(i)
            record["track_id"] = int(tid) if tid is not None else None
        records.append(record)
    return records


# --- zoom inset --------------------------------------------------------------------
def top_centers(detections: sv.Detections, n: int) -> list[tuple[float, float]]:
    """Centres of the ``n`` highest-confidence Detections, confidence-descending.

    Empty (or confidence-less) Detections yield ``[]`` — the caller draws no panels.
    """
    if len(detections) == 0 or detections.confidence is None:
        return []
    conf = np.asarray(detections.confidence)
    order = np.argsort(conf)[::-1][:n]  # confidence-descending, capped at n
    centers: list[tuple[float, float]] = []
    for i in order:
        x1, y1, x2, y2 = detections.xyxy[i]
        centers.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0))
    return centers


def _ema_center(
    target: tuple[float, float], prev: tuple[float, float] | None
) -> tuple[float, float]:
    """EMA the centre toward ``target`` (``prev is None`` snaps to ``target``)."""
    if prev is None:
        return target
    a = ZOOM_EMA_ALPHA
    return (a * target[0] + (1 - a) * prev[0], a * target[1] + (1 - a) * prev[1])


def _smooth_center(
    target: tuple[float, float] | None, prev: tuple[float, float] | None
) -> tuple[float, float] | None:
    """EMA the inset centre toward ``target``; ``None`` resets (WYSIWYG — no hold-last)."""
    if target is None:
        return None  # empty frame -> drop the inset; reappearing bird snaps, no drift
    return _ema_center(target, prev)


def _draw_one_panel(
    canvas: np.ndarray,
    source_frame: np.ndarray,
    center: tuple[float, float],
    zoom_size: float,
    frame_wh: tuple[int, int],
    panel: int,
    top: int,
) -> None:
    """Composite one magnified crop into the right-edge slot starting at row ``top``."""
    fw, fh = frame_wh
    crop = max(ZOOM_MIN_CROP_PX, int(zoom_size * fw))
    crop = min(crop, fh, fw)
    x1 = int(np.clip(center[0] - crop / 2, 0, fw - crop))
    y1 = int(np.clip(center[1] - crop / 2, 0, fh - crop))
    region = source_frame[y1 : y1 + crop, x1 : x1 + crop]
    region = cv2.resize(region, (panel, panel), interpolation=cv2.INTER_LINEAR)
    canvas[top : top + panel, fw - panel : fw] = region
    cv2.rectangle(canvas, (fw - panel, top), (fw - 1, top + panel - 1), ZOOM_BORDER_BGR, 2)


def draw_zoom_panels(
    canvas: np.ndarray,
    source_frame: np.ndarray,
    centers: list[tuple[float, float]],
    zoom_size: float,
    frame_wh: tuple[int, int],
    zoom_max: int,
) -> np.ndarray:
    """Composite up to ``zoom_max`` magnified crops as a strip down the right edge.

    Panel side = ``min(0.25*fw, fh // zoom_max)``, so slots are a fixed size for a given
    ``zoom_max`` and frames with fewer detections simply draw fewer panels (WYSIWYG). At
    ``zoom_max == 1`` this is the single top-right inset.
    """
    if not centers:
        return canvas  # no detections this frame -> no strip
    fw, fh = frame_wh
    panel = min(int(ZOOM_PANEL_FRACTION * fw), fh // max(1, zoom_max))
    for k, center in enumerate(centers):
        _draw_one_panel(canvas, source_frame, center, zoom_size, frame_wh, panel, k * panel)
    return canvas


# --- identity-mode zoom (ADR-0007) -------------------------------------------------
@dataclass(frozen=True)
class SlotRender:
    """One identity-mode Zoom Slot to draw: a crop (``center`` set) or black (``None``)."""

    index: int  # fixed slot position (vertical order in the strip)
    track_id: int  # the Track this slot is bound to
    center: tuple[float, float] | None  # EMA-smoothed crop centre, or None -> black panel


class ZoomSlots:
    """Identity-pinned Zoom Slot manager (ADR-0007).

    Binds each ``tracker_id`` to a fixed slot in first-seen order (or a single forced id),
    EMA-smooths each slot's crop centre, draws black while a Track is lost-but-alive, and
    frees a slot only once the id is gone longer than ``buffer`` (sharing ByteTrack's
    ``lost_track_buffer``). Stateful by nature, like ``sv.ByteTrack``/``sv.TraceAnnotator``.
    """

    def __init__(self, max_slots: int, buffer: int, forced_id: int | None = None) -> None:
        self._max = 1 if forced_id is not None else max_slots
        self._buffer = buffer
        self._forced_id = forced_id
        self._slots: list[int | None] = []  # slot index -> bound tracker_id (None = free)
        self._last_seen: dict[int, int] = {}  # tracker_id -> last frame it was present
        self._ema: dict[int, tuple[float, float]] = {}  # tracker_id -> smoothed centre

    @property
    def capacity(self) -> int:
        """Number of slots in the strip (1 in forced-id mode), for panel sizing."""
        return self._max

    def update(
        self, present: dict[int, tuple[float, float]], frame_idx: int
    ) -> list[SlotRender]:
        """Advance one frame given the confirmed Tracks present (id -> centre)."""
        slotted = {tid for tid in self._slots if tid is not None}
        for tid in slotted & present.keys():  # refresh present, slotted Tracks
            self._last_seen[tid] = frame_idx
            self._ema[tid] = _ema_center(present[tid], self._ema.get(tid))
        for tid in slotted - present.keys():  # missing -> drop EMA so reappearance snaps
            self._ema.pop(tid, None)
        self._free_expired(frame_idx)
        self._assign(present, frame_idx)
        return self._render()

    def _free_expired(self, frame_idx: int) -> None:
        for i, tid in enumerate(self._slots):
            if tid is not None and frame_idx - self._last_seen.get(tid, frame_idx) > self._buffer:
                self._slots[i] = None
                self._last_seen.pop(tid, None)
                self._ema.pop(tid, None)

    def _assign(self, present: dict[int, tuple[float, float]], frame_idx: int) -> None:
        slotted = {tid for tid in self._slots if tid is not None}
        if self._forced_id is not None:
            if self._forced_id in present and self._forced_id not in slotted:
                self._bind(self._forced_id, present[self._forced_id], frame_idx)
            return
        # ByteTrack ids are monotonic, so ascending id == first-seen order.
        for tid in sorted(tid for tid in present if tid not in slotted):
            if not self._bind(tid, present[tid], frame_idx):
                break  # no free slot -> first-seen wins, new birds wait

    def _bind(self, tid: int, center: tuple[float, float], frame_idx: int) -> bool:
        idx = self._free_index()
        if idx is None:
            return False
        self._slots[idx] = tid
        self._last_seen[tid] = frame_idx
        self._ema[tid] = center  # first bind snaps to the true centre (no drift-in)
        return True

    def _free_index(self) -> int | None:
        for i, tid in enumerate(self._slots):
            if tid is None:
                return i
        if len(self._slots) < self._max:
            self._slots.append(None)
            return len(self._slots) - 1
        return None

    def _render(self) -> list[SlotRender]:
        return [
            SlotRender(index=i, track_id=tid, center=self._ema.get(tid))
            for i, tid in enumerate(self._slots)
            if tid is not None
        ]


def _slot_label_scale(panel: int) -> float:
    return max(ZOOM_LABEL_MIN_SCALE, ZOOM_LABEL_SCALE * panel)


def _draw_slot_label(canvas: np.ndarray, track_id: int, fw: int, panel: int, top: int) -> None:
    """Draw the ``#id`` label inside a slot's top-left corner (resolution-relative)."""
    scale = _slot_label_scale(panel)
    cv2.putText(
        canvas,
        f"#{track_id}",
        (fw - panel + 4, top + int(18 * scale) + 6),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        ZOOM_BORDER_BGR,
        1,
        cv2.LINE_AA,
    )


def _draw_black_panel(canvas: np.ndarray, fw: int, panel: int, top: int) -> None:
    """Render a lost Track's slot in place: black fill + border (label drawn by caller)."""
    canvas[top : top + panel, fw - panel : fw] = 0
    cv2.rectangle(canvas, (fw - panel, top), (fw - 1, top + panel - 1), ZOOM_BORDER_BGR, 2)


def draw_identity_panels(
    canvas: np.ndarray,
    source_frame: np.ndarray,
    renders: list[SlotRender],
    zoom_size: float,
    frame_wh: tuple[int, int],
    max_slots: int,
) -> np.ndarray:
    """Composite identity-pinned slots down the right edge (ADR-0007).

    Each slot keeps a fixed vertical position (``index``); a present Track draws its crop,
    a lost-but-alive Track draws a black panel. Both carry the ``#id`` label. Panel size
    matches the confidence-mode strip so the two modes look identical apart from content.
    """
    if not renders:
        return canvas  # nothing bound yet -> no strip
    fw, fh = frame_wh
    panel = min(int(ZOOM_PANEL_FRACTION * fw), fh // max(1, max_slots))
    for r in renders:
        top = r.index * panel
        if r.center is None:
            _draw_black_panel(canvas, fw, panel, top)
        else:
            _draw_one_panel(canvas, source_frame, r.center, zoom_size, frame_wh, panel, top)
        _draw_slot_label(canvas, r.track_id, fw, panel, top)
    return canvas


# --- loop --------------------------------------------------------------------------
@dataclass(frozen=True)
class _TrackAnnotators:
    """Confirmed-track video annotators (coloured by ``tracker_id``)."""

    box: sv.BoxAnnotator
    label: sv.LabelAnnotator
    trace: sv.TraceAnnotator


def _build_track_annotators(frame_wh: tuple[int, int]) -> _TrackAnnotators:
    thickness = sv.calculate_optimal_line_thickness(resolution_wh=frame_wh)
    text_scale = sv.calculate_optimal_text_scale(resolution_wh=frame_wh)
    track = sv.ColorLookup.TRACK
    return _TrackAnnotators(
        box=sv.BoxAnnotator(thickness=thickness, color_lookup=track),
        label=sv.LabelAnnotator(
            text_scale=text_scale, text_thickness=max(1, thickness - 1), color_lookup=track
        ),
        trace=sv.TraceAnnotator(thickness=thickness, color_lookup=track),
    )


def _build_track_map(confirmed: sv.Detections) -> dict[int, int]:
    """Exact ``raw_row -> track_id`` map via the ``_idx`` stashed before tracking."""
    if confirmed.tracker_id is None or "_idx" not in confirmed.data:
        return {}
    return {
        int(raw_idx): int(tid)
        for raw_idx, tid in zip(confirmed.data["_idx"], confirmed.tracker_id)
    }


def _present_centers(confirmed: sv.Detections) -> dict[int, tuple[float, float]]:
    """``tracker_id -> box centre`` for the confirmed Tracks present this frame."""
    if confirmed.tracker_id is None:
        return {}
    centers: dict[int, tuple[float, float]] = {}
    for i, tid in enumerate(confirmed.tracker_id):
        x1, y1, x2, y2 = confirmed.xyxy[i]
        centers[int(tid)] = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
    return centers


def _track_frame(
    byte_track: _ByteTracker, detections: sv.Detections
) -> tuple[sv.Detections, dict[int, int]]:
    """Run ByteTrack on the raw detections; return confirmed Tracks + the id-join map."""
    detections.data["_idx"] = np.arange(len(detections))
    confirmed = byte_track.update_with_detections(detections)
    return confirmed, _build_track_map(confirmed)


def _annotate_confirmed(
    frame: np.ndarray, confirmed: sv.Detections, ann: _TrackAnnotators
) -> np.ndarray:
    """Draw confirmed Tracks: trail + box + ``#id`` label (the ADR-0004 filtered view)."""
    scene = frame.copy()
    if confirmed.tracker_id is None or len(confirmed) == 0:
        return scene
    labels = [f"#{int(t)}" for t in confirmed.tracker_id]
    scene = ann.trace.annotate(scene, confirmed)
    scene = ann.box.annotate(scene, confirmed)
    # sv.LabelAnnotator.annotate is mis-stubbed as PIL-only; it accepts/returns ndarray.
    labelled = ann.label.annotate(scene, confirmed, labels=labels)  # pyright: ignore
    return cast(np.ndarray, labelled)


def _confidence_zoom(
    canvas: np.ndarray,
    frame: np.ndarray,
    detections: sv.Detections,
    zoom: ZoomConfig,
    frame_wh: tuple[int, int],
    prev_center: tuple[float, float] | None,
) -> tuple[float, float] | None:
    """Confidence-mode inset (``--no-track``, ADR-0005); returns the new smoothed centre."""
    centers = top_centers(detections, zoom.max_panels)
    new_center = _smooth_center(centers[0] if centers else None, prev_center)
    if centers:
        centers = [new_center, *centers[1:]]  # slot 0 smoothed, rest raw
    draw_zoom_panels(canvas, frame, centers, zoom.size, frame_wh, zoom.max_panels)
    return new_center


@dataclass(frozen=True)
class _TrackRuntime:
    """Per-run tracking state, set together iff ``--track`` (keeps the loop branch-clean)."""

    byte_track: _ByteTracker
    ann: _TrackAnnotators
    slots: ZoomSlots | None  # None when --no-zoom


def _build_track_runtime(
    zoom: ZoomConfig, track: TrackConfig, frame_wh: tuple[int, int], fps: int
) -> _TrackRuntime:
    with warnings.catch_warnings():
        # sv.ByteTrack is deprecated (removed in supervision 0.30); we pin <0.30 and use it
        # per ADR-0006. Silence the FutureWarning so it doesn't pollute the run output.
        warnings.simplefilter("ignore", FutureWarning)
        byte_track = sv.ByteTrack(
            track_activation_threshold=track.activation,
            lost_track_buffer=track.buffer,
            frame_rate=fps,
        )
    slots = (
        ZoomSlots(zoom.max_panels, track.buffer, forced_id=zoom.track_id)
        if zoom.enabled
        else None
    )
    return _TrackRuntime(byte_track, _build_track_annotators(frame_wh), slots)


def run(
    cfg: DetectConfig, paths: RunPaths, weights: str, zoom: ZoomConfig, track: TrackConfig
) -> None:
    video_info = sv.VideoInfo.from_video_path(str(paths.source))
    frame_wh = video_info.resolution_wh

    model = YOLO(weights)
    detect = make_detector(model, cfg)
    box_annotator = sv.BoxAnnotator(
        thickness=sv.calculate_optimal_line_thickness(resolution_wh=frame_wh)
    )
    rt = (
        _build_track_runtime(zoom, track, frame_wh, round(video_info.fps))
        if track.enabled
        else None
    )

    paths.output.parent.mkdir(parents=True, exist_ok=True)
    paths.sidecar.parent.mkdir(parents=True, exist_ok=True)

    frames = sv.get_video_frames_generator(str(paths.source))
    zoom_center = None
    with sv.VideoSink(str(paths.output), video_info) as sink, open(
        paths.sidecar, "w", buffering=1
    ) as sidecar:
        for idx, frame in enumerate(tqdm(frames, total=video_info.total_frames, unit="f")):
            detections = detect(frame)
            if rt is not None:
                confirmed, track_map = _track_frame(rt.byte_track, detections)
                records = detection_records(detections, track_map)
                annotated = _annotate_confirmed(frame, confirmed, rt.ann)
                if rt.slots is not None:
                    renders = rt.slots.update(_present_centers(confirmed), idx)
                    annotated = draw_identity_panels(
                        annotated, frame, renders, zoom.size, frame_wh, rt.slots.capacity
                    )
            else:
                records = detection_records(detections)
                annotated = box_annotator.annotate(scene=frame.copy(), detections=detections)
                if zoom.enabled:
                    zoom_center = _confidence_zoom(
                        annotated, frame, detections, zoom, frame_wh, zoom_center
                    )
            sidecar.write(json.dumps({"frame": idx, "detections": records}) + "\n")
            sink.write_frame(annotated)


# --- cli ---------------------------------------------------------------------------
def _derive_paths(source: Path, output: str | None, sidecar: str | None) -> RunPaths:
    out = Path(output) if output else source.parent / f"{source.stem}.annotated.mp4"
    side = Path(sidecar) if sidecar else source.parent / f"{source.stem}.detections.jsonl"
    return RunPaths(source=source, output=out, sidecar=side)


def _resolve_classes(args, weights_is_default: bool) -> tuple[int, ...] | None:
    if args.classes is not None:
        return tuple(args.classes)
    if weights_is_default:
        return (COCO_BIRD_CLASS_ID,)  # COCO default -> birds only
    return None  # custom weights -> keep all classes


def validation_error(
    zoom_size: float,
    zoom_max: int,
    *,
    track: bool = True,
    track_buffer: int = DEFAULT_TRACK_BUFFER,
    track_activation: float = DEFAULT_TRACK_ACTIVATION,
    zoom_track_id: int | None = None,
) -> str | None:
    """Return a user-facing message for an invalid arg combination, else ``None``."""
    if not 0.0 < zoom_size <= 1.0:
        return "--zoom-size must be in (0, 1]"
    if zoom_max < 1:
        return "--zoom-max must be >= 1"
    if track_buffer < 1:
        return "--track-buffer must be >= 1"
    if not 0.0 < track_activation <= 1.0:
        return "--track-activation must be in (0, 1]"
    if zoom_track_id is not None and not track:
        return "--zoom-track-id requires --track (it can't follow an id with --no-track)"
    return None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="detect-birds", description=__doc__)
    p.add_argument("--source", required=True, help="Input video file")
    p.add_argument("--weights", default=DEFAULT_WEIGHTS, help="YOLO weights (.pt)")
    p.add_argument("--device", default="auto", help="auto | cpu | mps | cuda | cuda:0")
    p.add_argument("--conf", type=float, default=DEFAULT_CONF, help="Confidence threshold")
    p.add_argument("--classes", type=int, nargs="+", default=None, help="Class ids to keep")
    p.add_argument("--slice", dest="slice", action=argparse.BooleanOptionalAction, default=True,
                   help="Toggle sliced inference (default: on)")
    p.add_argument("--slice-wh", type=int, nargs=2, default=list(DEFAULT_SLICE_WH),
                   metavar=("W", "H"), help="Slice size in px")
    p.add_argument("--overlap-ratio", type=float, nargs=2, default=list(DEFAULT_OVERLAP_RATIO),
                   metavar=("W", "H"), help="Slice overlap ratio")
    p.add_argument("--overlap-filter", choices=["nms", "nmm"], default="nms",
                   help="Slice merge strategy")
    p.add_argument("--thread-workers", type=int, default=DEFAULT_THREAD_WORKERS,
                   help="Parallel slice inference workers")
    p.add_argument("--zoom", action=argparse.BooleanOptionalAction, default=True,
                   help="Picture-in-picture zoom inset (default: on)")
    p.add_argument("--zoom-size", type=float, default=DEFAULT_ZOOM_SIZE,
                   help="Zoom crop side as fraction of frame width")
    p.add_argument("--zoom-max", type=int, default=1,
                   help="Follow up to N detections (top-N by confidence); default 1")
    p.add_argument("--track", action=argparse.BooleanOptionalAction, default=True,
                   help="In-loop sv.ByteTrack tracking (default: on)")
    p.add_argument("--track-buffer", type=int, default=DEFAULT_TRACK_BUFFER,
                   help="lost_track_buffer: frames a lost id (and its zoom slot) is held")
    p.add_argument("--track-activation", type=float, default=DEFAULT_TRACK_ACTIVATION,
                   help="track_activation_threshold: min conf to start a track")
    p.add_argument("--zoom-track-id", type=int, default=None,
                   help="Lock the zoom inset to one tracker_id (single-object; implies --track)")
    p.add_argument("--output", default=None, help="Annotated video path")
    p.add_argument("--sidecar", default=None, help="JSONL detections sidecar path")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    source = Path(args.source)
    if not source.exists():
        print(f"error: source video not found: {source}", file=sys.stderr)
        return 1
    try:
        sv.VideoInfo.from_video_path(str(source))
    except Exception as exc:  # noqa: BLE001 - surface any decode/open failure clearly
        print(f"error: could not open video '{source}': {exc}", file=sys.stderr)
        return 1
    err = validation_error(
        args.zoom_size,
        args.zoom_max,
        track=args.track,
        track_buffer=args.track_buffer,
        track_activation=args.track_activation,
        zoom_track_id=args.zoom_track_id,
    )
    if err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    cfg = DetectConfig(
        conf=args.conf,
        classes=_resolve_classes(args, args.weights == DEFAULT_WEIGHTS),
        device=resolve_device(args.device),
        use_slicing=args.slice,
        slice_wh=tuple(args.slice_wh),
        overlap_ratio_wh=tuple(args.overlap_ratio),
        overlap_filter=args.overlap_filter,
        thread_workers=args.thread_workers,
    )
    paths = _derive_paths(source, args.output, args.sidecar)

    zoom = ZoomConfig(
        enabled=args.zoom,
        size=args.zoom_size,
        max_panels=args.zoom_max,
        track_id=args.zoom_track_id,
    )
    track = TrackConfig(
        enabled=args.track, activation=args.track_activation, buffer=args.track_buffer
    )
    print(f"device={cfg.device} slicing={'on' if cfg.use_slicing else 'off'} "
          f"conf={cfg.conf} classes={cfg.classes} "
          f"track={'on' if track.enabled else 'off'} "
          f"zoom={'on' if zoom.enabled else 'off'} zoom_max={zoom.max_panels}"
          + (f" zoom_track_id={zoom.track_id}" if zoom.track_id is not None else ""))
    run(cfg, paths, args.weights, zoom, track)
    print(f"wrote {paths.output}\nwrote {paths.sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
