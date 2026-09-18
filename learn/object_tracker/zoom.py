"""Zoom Inset rendering: confidence-mode strip + identity-pinned slots (ADR-0005/0007).

Week 7. Two modes over one strip:

* **Confidence mode** (``--no-track``): each frame's N highest-confidence Detections. No
  cross-frame identity, so panels reorder and flicker. That limitation is ADR-0005.
* **Identity mode** (``--track``): each panel binds to a Track and owns a **fixed slot** for
  that Track's life. The strip never reflows; a temporarily-missing Track draws black in
  place, and the slot frees only after the hold elapses. That is ADR-0007.

**The cv2 raster work below is given to you** — cropping, resizing, borders, labels, panel
geometry. It is arithmetic, not insight. What you implement is the *decision* logic: who gets
a slot, who keeps it, who loses it, and which centres get drawn.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
import supervision as sv

from .config import (
    ZOOM_BORDER_BGR,
    ZOOM_BORDER_THICKNESS,
    ZOOM_EMA_ALPHA,
    ZOOM_LABEL_MIN_SCALE,
    ZOOM_LABEL_SCALE,
    ZOOM_MIN_CROP_PX,
    ZOOM_PANEL_FRACTION,
    ZoomConfig,
)


# --- YOU IMPLEMENT -----------------------------------------------------------------
def top_centers(detections: sv.Detections, n: int) -> list[tuple[float, float]]:
    """Centres of the ``n`` highest-confidence Detections, confidence-descending.

    Empty (or confidence-less) Detections yield ``[]`` — the caller draws no panels.
    """
    raise NotImplementedError("Week 7 — see learn/curriculum/week-07-zoom-slots.md")


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



# --- GIVEN: the cv2 raster (crop, resize, border, label, geometry) -------------------
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
    cv2.rectangle(
        canvas, (fw - panel, top), (fw - 1, top + panel - 1), ZOOM_BORDER_BGR, ZOOM_BORDER_THICKNESS
    )


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


@dataclass(frozen=True)
class SlotRender:
    """One identity-mode Zoom Slot to draw: a crop (``center`` set) or black (``None``)."""

    index: int  # fixed slot position (vertical order in the strip)
    track_id: int  # the Track this slot is bound to
    center: tuple[float, float] | None  # EMA-smoothed crop centre, or None -> black panel


# --- YOU IMPLEMENT: the slot state machine (the lesson of the week) ------------------
class ZoomSlots:
    """Identity-pinned Zoom Slot manager (ADR-0007).

    Binds each ``tracker_id`` to a fixed slot in **first-seen order** (or a single forced
    id), EMA-smooths each slot's crop centre, draws black while a Track is lost-but-alive,
    and frees a slot only once the id has been gone longer than ``buffer``.

    Stateful by nature — but keep every *decision* in here and every *pixel* out. These
    methods should be testable with nothing but dicts and ints. If a test of this class needs
    a numpy array, the split is in the wrong place.

    Suggested internal state (you may choose otherwise, but you need something like it):
      * ``_slots``     — list index -> bound tracker_id, or None for a free slot
      * ``_last_seen`` — tracker_id -> the last frame index it was present
      * ``_ema``       — tracker_id -> smoothed crop centre

    Two details worth getting right:
      * A Track that goes missing should **drop its EMA**, so reappearing snaps to the true
        centre rather than sliding in from where it used to be.
      * Slot assignment walks present ids in **ascending** order. Tracker ids are monotonic,
        so ascending id *is* first-seen order — the same trick ``target_selector`` uses in
        week 11. When slots run out, first-seen wins and newcomers wait.
    """

    def __init__(self, max_slots: int, buffer: int, forced_id: int | None = None) -> None:
        raise NotImplementedError("Week 7 — see learn/curriculum/week-07-zoom-slots.md")

    @property
    def capacity(self) -> int:
        """Number of slots in the strip (1 in forced-id mode), for panel sizing."""
        raise NotImplementedError("Week 7 — see learn/curriculum/week-07-zoom-slots.md")

    def update(
        self, present: dict[int, tuple[float, float]], frame_idx: int
    ) -> list[SlotRender]:
        """Advance one frame given the confirmed Tracks present (id -> centre).

        Roughly: refresh the present-and-slotted, drop the EMA of the missing, free anything
        past its hold, assign free slots to unslotted present ids, then render.
        """
        raise NotImplementedError("Week 7 — see learn/curriculum/week-07-zoom-slots.md")


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
    cv2.rectangle(
        canvas, (fw - panel, top), (fw - 1, top + panel - 1), ZOOM_BORDER_BGR, ZOOM_BORDER_THICKNESS
    )


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



# --- YOU IMPLEMENT -----------------------------------------------------------------
def _confidence_zoom(
    canvas: np.ndarray,
    frame: np.ndarray,
    detections: sv.Detections,
    zoom: ZoomConfig,
    frame_wh: tuple[int, int],
    prev_center: tuple[float, float] | None,
) -> tuple[float, float] | None:
    """Confidence-mode inset (``--no-track``, ADR-0005); returns the new smoothed centre.

    Take this frame's top-N centres, smooth **slot 0 only** (the others are raw — think
    about why smoothing a slot whose occupant changes every frame would be worse than not),
    draw the strip, and hand the new centre back for the next frame to smooth against.
    """
    raise NotImplementedError("Week 7 — see learn/curriculum/week-07-zoom-slots.md")
