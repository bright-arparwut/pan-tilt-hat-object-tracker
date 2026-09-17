"""Appearance factory (ADR-0011): build the supervision annotators from the constants.

Every knob lives in ``config.py`` under the ``Appearance`` banner — deliberately not
``--flags``, not a separate file, and not an external config format. This module is the only
reader of those constants, so editing one constant is the only thing that changes the look.

Sizes are **resolution-relative**: a 2px outline is right at 640p and invisible at 4K, so
thickness and text scale are computed from the frame size via supervision's
``calculate_optimal_*`` helpers, then multiplied by the ``*_SCALE`` constants.
"""

from __future__ import annotations

from typing import Union

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

# The union of everything a DETECTION_STYLE can build. They share no common base class in
# supervision, only an ``annotate(scene, detections) -> scene`` shape.
DetectionAnn = Union[
    sv.BoxAnnotator,
    sv.RoundBoxAnnotator,
    sv.BoxCornerAnnotator,
    sv.CircleAnnotator,
    sv.EllipseAnnotator,
    sv.ColorAnnotator,
    sv.DotAnnotator,
    sv.TriangleAnnotator,
    sv.BlurAnnotator,
    sv.PixelateAnnotator,
]


def _resolve_lookup(mode_default: sv.ColorLookup) -> sv.ColorLookup:
    """``COLOR_LOOKUP_OVERRIDE`` when set, else the caller's mode-appropriate default.

    Without tracking, colour by ``CLASS``; with tracking, colour by ``TRACK`` so each
    identity keeps its own colour across frames.
    """
    raise NotImplementedError("Week 3 — see learn/curriculum/week-03-annotation-sidecar.md")


def build_detection_annotator(
    frame_wh: tuple[int, int],
    color_lookup: sv.ColorLookup = sv.ColorLookup.CLASS,
) -> DetectionAnn:
    """Build the annotator named by ``DETECTION_STYLE``, sized for this frame.

    The ten styles **do not share a constructor** — ``BlurAnnotator`` and
    ``PixelateAnnotator`` take no colour at all, ``DotAnnotator`` takes a radius rather than a
    thickness, and so on. So this cannot be a one-line dict lookup of ``cls(**kwargs)``. Work
    out a shape that keeps each style's construction honest without a ten-branch ``if``.
    """
    raise NotImplementedError("Week 3 — see learn/curriculum/week-03-annotation-sidecar.md")


def build_label_annotator(
    frame_wh: tuple[int, int],
    color_lookup: sv.ColorLookup = sv.ColorLookup.CLASS,
) -> sv.LabelAnnotator:
    """Build the ``#id`` / class label annotator, text-scaled for this frame."""
    raise NotImplementedError("Week 3 — see learn/curriculum/week-03-annotation-sidecar.md")


def build_trace_annotator(
    frame_wh: tuple[int, int],
    color_lookup: sv.ColorLookup = sv.ColorLookup.TRACK,
) -> sv.TraceAnnotator:
    """Build the motion-trail annotator (``TRACE_LENGTH`` frames of history).

    Only meaningful under tracking — a trail needs an identity to follow.
    """
    raise NotImplementedError("Week 6 — see learn/curriculum/week-06-bytetrack.md")
