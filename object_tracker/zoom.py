"""Zoom Inset rendering: confidence-mode strip + identity-pinned slots (ADR-0005/0007)."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
import supervision as sv

from .config import (
    ZOOM_BORDER_BGR,
    ZOOM_EMA_ALPHA,
    ZOOM_LABEL_MIN_SCALE,
    ZOOM_LABEL_SCALE,
    ZOOM_MIN_CROP_PX,
    ZOOM_PANEL_FRACTION,
    ZoomConfig,
)


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
        return None  # empty frame -> drop the inset; reappearing object snaps, no drift
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
                break  # no free slot -> first-seen wins, new tracks wait

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
