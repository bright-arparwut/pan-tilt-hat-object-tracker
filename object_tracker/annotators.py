"""Themed annotator factory: build the ``sv.*Annotator``s from the Appearance constants.

One place constructs the supervision annotators so the no-track path (``pipeline.py``) and
the track path (``tracking.py``) can't drift in style (ADR-0011). The look comes from the
Appearance block in ``config.py``; ``thickness`` / ``text_scale`` stay resolution-derived
(``sv.calculate_optimal_*``) and the constants only nudge them, so the defaults reproduce the
prior, un-themed construction byte-for-byte. Supervision-only by design — the cv2 zoom raster
reads its ``ZOOM_*`` constants directly in ``zoom.py``.
"""

from __future__ import annotations

from typing import Callable

import supervision as sv

from .config import (
    ANNOTATION_PALETTE,
    COLOR_LOOKUP_OVERRIDE,
    DETECTION_STYLE,
    LABEL_POSITION,
    LABEL_TEXT_COLOR,
    TEXT_SCALE_MULT,
    THICKNESS_SCALE,
    TRACE_LENGTH,
    TRACE_POSITION,
    DetectionStyle,
)

# Every annotator a DetectionStyle can resolve to (ADR-0011 "Detection style"). They do not
# share a constructor — box outlines take (color, thickness), fills/markers take (color) only,
# and Blur/Pixelate take no colour at all — so each style is built by its own callable in
# ``_DETECTION_STYLES`` below, not a single uniform constructor. ``DetectionAnn`` is a
# public-API union (preferred over the non-public base class), kept beside the map for sync.
DetectionAnn = (
    sv.BoxAnnotator
    | sv.RoundBoxAnnotator
    | sv.BoxCornerAnnotator
    | sv.CircleAnnotator
    | sv.EllipseAnnotator
    | sv.ColorAnnotator
    | sv.DotAnnotator
    | sv.TriangleAnnotator
    | sv.BlurAnnotator
    | sv.PixelateAnnotator
)
_StyleBuilder = Callable[[tuple[int, int], sv.ColorLookup], DetectionAnn]


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


# --- per-style builders: one constructor shape each (grouped by what they accept) ---
def _outline(cls: Callable[..., DetectionAnn]) -> _StyleBuilder:
    """Box-outline shapes: palette colour + resolution-scaled thickness + lookup."""
    return lambda frame_wh, color_lookup: cls(
        color=ANNOTATION_PALETTE,
        thickness=_thickness(frame_wh),
        color_lookup=_lookup(color_lookup),
    )


def _filled(cls: Callable[..., DetectionAnn]) -> _StyleBuilder:
    """Fill/marker shapes: palette colour + lookup; extents (opacity/radius/…) on sv defaults."""
    return lambda frame_wh, color_lookup: cls(
        color=ANNOTATION_PALETTE, color_lookup=_lookup(color_lookup)
    )


def _effect(cls: Callable[..., DetectionAnn]) -> _StyleBuilder:
    """Anonymising effects: no colour/lookup contract; kernel/pixel size on sv defaults."""
    return lambda frame_wh, color_lookup: cls()


_DETECTION_STYLES: dict[DetectionStyle, _StyleBuilder] = {
    DetectionStyle.BOX: _outline(sv.BoxAnnotator),
    DetectionStyle.ROUND: _outline(sv.RoundBoxAnnotator),
    DetectionStyle.CORNER: _outline(sv.BoxCornerAnnotator),
    DetectionStyle.CIRCLE: _outline(sv.CircleAnnotator),
    DetectionStyle.ELLIPSE: _outline(sv.EllipseAnnotator),
    DetectionStyle.COLOR: _filled(sv.ColorAnnotator),
    DetectionStyle.DOT: _filled(sv.DotAnnotator),
    DetectionStyle.TRIANGLE: _filled(sv.TriangleAnnotator),
    DetectionStyle.BLUR: _effect(sv.BlurAnnotator),
    DetectionStyle.PIXELATE: _effect(sv.PixelateAnnotator),
}


def build_detection_annotator(
    frame_wh: tuple[int, int], color_lookup: sv.ColorLookup = sv.ColorLookup.CLASS
) -> DetectionAnn:
    """The annotator for the configured ``DETECTION_STYLE`` (ADR-0011); ``color_lookup`` is
    the mode default (CLASS no-track, TRACK track). Each style builds itself via
    ``_DETECTION_STYLES``; Blur/Pixelate ignore ``color_lookup`` and the palette."""
    return _DETECTION_STYLES[DETECTION_STYLE](frame_wh, color_lookup)


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
