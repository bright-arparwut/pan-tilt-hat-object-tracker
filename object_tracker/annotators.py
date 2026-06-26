"""Themed annotator factory: build the ``sv.*Annotator``s from the Appearance constants.

One place constructs the supervision annotators so the no-track path (``pipeline.py``) and
the track path (``tracking.py``) can't drift in style (ADR-0011). The look comes from the
Appearance block in ``config.py``; ``thickness`` / ``text_scale`` stay resolution-derived
(``sv.calculate_optimal_*``) and the constants only nudge them, so the defaults reproduce the
prior, un-themed construction byte-for-byte. Supervision-only by design — the cv2 zoom raster
reads its ``ZOOM_*`` constants directly in ``zoom.py``.
"""

from __future__ import annotations

import supervision as sv

from .config import (
    ANNOTATION_PALETTE,
    COLOR_LOOKUP_OVERRIDE,
    LABEL_POSITION,
    LABEL_TEXT_COLOR,
    TEXT_SCALE_MULT,
    THICKNESS_SCALE,
    TRACE_LENGTH,
    TRACE_POSITION,
)


def _thickness(frame_wh: tuple[int, int]) -> int:
    """Resolution-optimal line thickness, nudged by ``THICKNESS_SCALE`` (1.0 = unchanged)."""
    optimal = sv.calculate_optimal_line_thickness(resolution_wh=frame_wh)
    return max(1, round(optimal * THICKNESS_SCALE))


def _text_scale(frame_wh: tuple[int, int]) -> float:
    """Resolution-optimal text scale, nudged by ``TEXT_SCALE_MULT`` (1.0 = unchanged)."""
    return sv.calculate_optimal_text_scale(resolution_wh=frame_wh) * TEXT_SCALE_MULT


def _lookup(default: sv.ColorLookup) -> sv.ColorLookup:
    """The mode's ``default`` lookup, unless ``COLOR_LOOKUP_OVERRIDE`` forces one for all."""
    return COLOR_LOOKUP_OVERRIDE if COLOR_LOOKUP_OVERRIDE is not None else default


def build_box_annotator(
    frame_wh: tuple[int, int], color_lookup: sv.ColorLookup = sv.ColorLookup.CLASS
) -> sv.BoxAnnotator:
    """Box annotator; ``color_lookup`` is the mode default (CLASS no-track, TRACK track)."""
    return sv.BoxAnnotator(
        color=ANNOTATION_PALETTE,
        thickness=_thickness(frame_wh),
        color_lookup=_lookup(color_lookup),
    )


def build_label_annotator(
    frame_wh: tuple[int, int], color_lookup: sv.ColorLookup = sv.ColorLookup.CLASS
) -> sv.LabelAnnotator:
    """``#id`` label annotator. ``LABEL_TEXT_COLOR`` is passed only when set (else sv default)."""
    kwargs = {
        "color": ANNOTATION_PALETTE,
        "text_scale": _text_scale(frame_wh),
        "text_thickness": max(1, _thickness(frame_wh) - 1),
        "text_position": LABEL_POSITION,
        "color_lookup": _lookup(color_lookup),
    }
    if LABEL_TEXT_COLOR is not None:
        kwargs["text_color"] = LABEL_TEXT_COLOR
    return sv.LabelAnnotator(**kwargs)


def build_trace_annotator(
    frame_wh: tuple[int, int], color_lookup: sv.ColorLookup = sv.ColorLookup.CLASS
) -> sv.TraceAnnotator:
    """Motion-trail annotator; ``TRACE_LENGTH`` sets the trail length in frames."""
    return sv.TraceAnnotator(
        color=ANNOTATION_PALETTE,
        thickness=_thickness(frame_wh),
        trace_length=TRACE_LENGTH,
        position=TRACE_POSITION,
        color_lookup=_lookup(color_lookup),
    )
