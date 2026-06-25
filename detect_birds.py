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
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import supervision as sv
from tqdm import tqdm
from ultralytics import YOLO

# --- defaults / constants (resolution-relative where it matters) -------------------
COCO_BIRD_CLASS_ID = 14
DEFAULT_WEIGHTS = "yolo11n.pt"
DEFAULT_CONF = 0.15  # recall-first; tracking is the false-positive filter (ADR-0004)
DEFAULT_SLICE_WH = (640, 640)
DEFAULT_OVERLAP_RATIO = (0.2, 0.2)
DEFAULT_THREAD_WORKERS = 4
DEFAULT_ZOOM_SIZE = 0.05  # crop side as a fraction of frame width
ZOOM_PANEL_FRACTION = 0.25  # inset panel side as a fraction of frame width
# effective magnification = ZOOM_PANEL_FRACTION / zoom_size (≈5x at defaults)
ZOOM_EMA_ALPHA = 0.3  # smoothing on the inset centre (lower = smoother)
ZOOM_BORDER_BGR = (0, 255, 0)
ZOOM_MIN_CROP_PX = 8  # floor on the crop side so tiny --zoom-size stays sampleable


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
class ZoomConfig:
    """Zoom Inset settings for a run (see CONTEXT.md: Zoom Inset / Zoom Panel)."""

    enabled: bool
    size: float  # crop side as a fraction of frame width
    max_panels: int  # follow the top-N detections by confidence (1 = single inset)


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
def detection_records(detections: sv.Detections) -> list[dict]:
    """Serialise detections to plain dicts (source-pixel xyxy)."""
    if len(detections) == 0:
        return []
    names = detections.data.get("class_name") if detections.data else None
    records = []
    for i in range(len(detections)):
        x1, y1, x2, y2 = (round(float(v), 1) for v in detections.xyxy[i])
        conf = detections.confidence[i] if detections.confidence is not None else None
        cls = detections.class_id[i] if detections.class_id is not None else None
        records.append(
            {
                "xyxy": [x1, y1, x2, y2],
                "conf": round(float(conf), 4) if conf is not None else None,
                "cls": int(cls) if cls is not None else None,
                "name": str(names[i]) if names is not None else None,
            }
        )
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


def _smooth_center(
    target: tuple[float, float] | None, prev: tuple[float, float] | None
) -> tuple[float, float] | None:
    """EMA the inset centre toward ``target``; ``None`` resets (WYSIWYG — no hold-last)."""
    if target is None:
        return None  # empty frame -> drop the inset; reappearing bird snaps, no drift
    if prev is None:
        return target
    a = ZOOM_EMA_ALPHA
    return (a * target[0] + (1 - a) * prev[0], a * target[1] + (1 - a) * prev[1])


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


# --- loop --------------------------------------------------------------------------
def run(cfg: DetectConfig, paths: RunPaths, weights: str, zoom: ZoomConfig) -> None:
    video_info = sv.VideoInfo.from_video_path(str(paths.source))
    frame_wh = video_info.resolution_wh

    model = YOLO(weights)
    detect = make_detector(model, cfg)
    box_annotator = sv.BoxAnnotator(
        thickness=sv.calculate_optimal_line_thickness(resolution_wh=frame_wh)
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
            sidecar.write(
                json.dumps({"frame": idx, "detections": detection_records(detections)}) + "\n"
            )
            annotated = box_annotator.annotate(scene=frame.copy(), detections=detections)
            if zoom.enabled:
                centers = top_centers(detections, zoom.max_panels)
                zoom_center = _smooth_center(centers[0] if centers else None, zoom_center)
                if centers:
                    centers = [zoom_center, *centers[1:]]  # slot 0 smoothed, rest raw
                annotated = draw_zoom_panels(
                    annotated, frame, centers, zoom.size, frame_wh, zoom.max_panels
                )
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


def validation_error(zoom_size: float, zoom_max: int) -> str | None:
    """Return a user-facing message for an invalid arg combination, else ``None``."""
    if not 0.0 < zoom_size <= 1.0:
        return "--zoom-size must be in (0, 1]"
    if zoom_max < 1:
        return "--zoom-max must be >= 1"
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
    err = validation_error(args.zoom_size, args.zoom_max)
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

    zoom = ZoomConfig(enabled=args.zoom, size=args.zoom_size, max_panels=args.zoom_max)
    print(f"device={cfg.device} slicing={'on' if cfg.use_slicing else 'off'} "
          f"conf={cfg.conf} classes={cfg.classes} "
          f"zoom={'on' if zoom.enabled else 'off'} zoom_max={zoom.max_panels}")
    run(cfg, paths, args.weights, zoom)
    print(f"wrote {paths.output}\nwrote {paths.sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
