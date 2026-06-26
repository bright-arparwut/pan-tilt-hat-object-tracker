"""Unit tests for the themed annotator factory (ADR-0011).

Covers ``build_detection`` / ``build_label`` / ``build_trace_annotator``: that the builders
thread the current Appearance constants (``THICKNESS_SCALE``, ``TEXT_SCALE_MULT``,
``LABEL_POSITION``, ``DETECTION_STYLE``, …) through to the supervision annotators, and that the
override knobs (``color_lookup`` / label-colour) take effect. Expected values are derived from
the live constants, so editing the theme re-baselines these tests rather than breaking them.
The knobs are monkeypatched on the ``annotators`` module, where the builders read them.

``DETECTION_STYLE`` is pinned per-test where an attribute of the built annotator is asserted,
so these stay green regardless of the live style (which spans outlines, fills and effects that
do not share a constructor — see ``test_detection_style_*``).
"""

from __future__ import annotations

import pytest
import supervision as sv

from object_tracker import annotators
from object_tracker.annotators import (
    build_detection_annotator,
    build_label_annotator,
    build_trace_annotator,
)
from object_tracker.config import DetectionStyle

FRAME_WH = (1920, 1080)  # (w, h)

# annotator groups by constructor contract — also used to narrow the DetectionAnn union so
# pyright knows the shared attributes (thickness/colour/lookup) exist before we assert them.
_OUTLINE_CLASSES = (
    sv.BoxAnnotator,
    sv.RoundBoxAnnotator,
    sv.BoxCornerAnnotator,
    sv.CircleAnnotator,
    sv.EllipseAnnotator,
)
_FILL_CLASSES = (sv.ColorAnnotator, sv.DotAnnotator, sv.TriangleAnnotator)


# --- builders thread the current Appearance theme through the factory --------------
def test_box_default_shape_matches_themed_thickness_and_class_lookup(monkeypatch):
    # pin the style this test is about (BOX); DETECTION_STYLE itself is exercised separately
    monkeypatch.setattr(annotators, "DETECTION_STYLE", DetectionStyle.BOX)
    optimal = sv.calculate_optimal_line_thickness(resolution_wh=FRAME_WH)
    box = build_detection_annotator(FRAME_WH)
    assert isinstance(box, sv.BoxAnnotator)  # the BOX style = the rectangle
    assert box.thickness == max(1, round(optimal * annotators.THICKNESS_SCALE))
    assert box.color_lookup == sv.ColorLookup.CLASS
    assert box.color == sv.ColorPalette.DEFAULT


def test_box_honours_explicit_color_lookup(monkeypatch):
    monkeypatch.setattr(annotators, "DETECTION_STYLE", DetectionStyle.BOX)
    box = build_detection_annotator(FRAME_WH, sv.ColorLookup.TRACK)
    assert isinstance(box, sv.BoxAnnotator)
    assert box.color_lookup == sv.ColorLookup.TRACK


def test_label_defaults_match_themed_scale_position_and_kept_text_color():
    optimal = sv.calculate_optimal_line_thickness(resolution_wh=FRAME_WH)
    themed_thickness = max(1, round(optimal * annotators.THICKNESS_SCALE))
    label = build_label_annotator(FRAME_WH)
    optimal_scale = sv.calculate_optimal_text_scale(resolution_wh=FRAME_WH)
    assert label.text_scale == optimal_scale * annotators.TEXT_SCALE_MULT
    assert label.text_thickness == max(1, themed_thickness - 1)
    assert label.text_anchor == annotators.LABEL_POSITION
    assert label.color_lookup == sv.ColorLookup.CLASS
    # LABEL_TEXT_COLOR is None by default -> supervision's white is kept, not overridden
    assert label.text_color == sv.Color.WHITE


def test_trace_defaults_carry_trace_length_and_themed_thickness():
    optimal = sv.calculate_optimal_line_thickness(resolution_wh=FRAME_WH)
    trace = build_trace_annotator(FRAME_WH)
    assert trace.trace.max_size == annotators.TRACE_LENGTH
    assert trace.trace.anchor == annotators.TRACE_POSITION
    assert trace.thickness == max(1, round(optimal * annotators.THICKNESS_SCALE))
    assert trace.color_lookup == sv.ColorLookup.CLASS


# --- the Appearance knobs take effect ----------------------------------------------
def test_thickness_scale_multiplies_optimal_thickness(monkeypatch):
    monkeypatch.setattr(annotators, "DETECTION_STYLE", DetectionStyle.BOX)
    base = sv.calculate_optimal_line_thickness(resolution_wh=FRAME_WH)
    monkeypatch.setattr(annotators, "THICKNESS_SCALE", 3.0)
    box = build_detection_annotator(FRAME_WH)
    assert isinstance(box, sv.BoxAnnotator)
    assert box.thickness == max(1, round(base * 3.0))


def test_text_scale_mult_multiplies_optimal_scale(monkeypatch):
    base = sv.calculate_optimal_text_scale(resolution_wh=FRAME_WH)
    monkeypatch.setattr(annotators, "TEXT_SCALE_MULT", 2.0)
    assert build_label_annotator(FRAME_WH).text_scale == base * 2.0


def test_color_lookup_override_beats_default_and_explicit_caller_lookup(monkeypatch):
    monkeypatch.setattr(annotators, "DETECTION_STYLE", DetectionStyle.BOX)
    monkeypatch.setattr(annotators, "COLOR_LOOKUP_OVERRIDE", sv.ColorLookup.INDEX)
    box = build_detection_annotator(FRAME_WH)
    forced = build_detection_annotator(FRAME_WH, sv.ColorLookup.TRACK)
    assert isinstance(box, sv.BoxAnnotator) and isinstance(forced, sv.BoxAnnotator)
    assert box.color_lookup == sv.ColorLookup.INDEX
    assert forced.color_lookup == sv.ColorLookup.INDEX  # override beats the explicit TRACK arg


def test_label_text_color_override_sets_text_color(monkeypatch):
    monkeypatch.setattr(annotators, "LABEL_TEXT_COLOR", sv.Color.RED)
    assert build_label_annotator(FRAME_WH).text_color == sv.Color.RED


def test_trace_length_override_sets_buffer_size(monkeypatch):
    monkeypatch.setattr(annotators, "TRACE_LENGTH", 7)
    assert build_trace_annotator(FRAME_WH).trace.max_size == 7


# --- DETECTION_STYLE selects the per-Detection annotator (ADR-0011 "Detection style") --
# Three constructor groups: outlines (colour + thickness + lookup), fills/markers
# (colour + lookup, no thickness), and effects (no colour contract at all).
@pytest.mark.parametrize(
    ("style", "expected_cls"),
    [
        (DetectionStyle.BOX, sv.BoxAnnotator),
        (DetectionStyle.ROUND, sv.RoundBoxAnnotator),
        (DetectionStyle.CORNER, sv.BoxCornerAnnotator),
        (DetectionStyle.CIRCLE, sv.CircleAnnotator),
        (DetectionStyle.ELLIPSE, sv.EllipseAnnotator),
    ],
)
def test_detection_style_outline_carries_thickness_colour_and_lookup(
    monkeypatch, style, expected_cls
):
    monkeypatch.setattr(annotators, "DETECTION_STYLE", style)
    box = build_detection_annotator(FRAME_WH, sv.ColorLookup.TRACK)
    assert type(box) is expected_cls
    assert isinstance(box, _OUTLINE_CLASSES)  # narrow to the shared (colour, thickness, lookup)
    assert box.thickness == annotators._thickness(FRAME_WH)  # the factory's scaled thickness
    assert box.color == sv.ColorPalette.DEFAULT
    assert box.color_lookup == sv.ColorLookup.TRACK


@pytest.mark.parametrize(
    ("style", "expected_cls"),
    [
        (DetectionStyle.COLOR, sv.ColorAnnotator),
        (DetectionStyle.DOT, sv.DotAnnotator),
        (DetectionStyle.TRIANGLE, sv.TriangleAnnotator),
    ],
)
def test_detection_style_fill_carries_colour_and_lookup_but_no_thickness(
    monkeypatch, style, expected_cls
):
    monkeypatch.setattr(annotators, "DETECTION_STYLE", style)
    mark = build_detection_annotator(FRAME_WH, sv.ColorLookup.TRACK)
    assert type(mark) is expected_cls
    assert isinstance(mark, _FILL_CLASSES)  # narrow to the (colour, lookup) contract
    assert mark.color == sv.ColorPalette.DEFAULT
    assert mark.color_lookup == sv.ColorLookup.TRACK
    assert not hasattr(mark, "thickness")  # fills/markers size themselves, not by line width


@pytest.mark.parametrize(
    ("style", "expected_cls"),
    [
        (DetectionStyle.BLUR, sv.BlurAnnotator),
        (DetectionStyle.PIXELATE, sv.PixelateAnnotator),
    ],
)
def test_detection_style_effect_ignores_colour_contract(monkeypatch, style, expected_cls):
    monkeypatch.setattr(annotators, "DETECTION_STYLE", style)
    # a forced lookup must not break construction even though effects ignore colour
    effect = build_detection_annotator(FRAME_WH, sv.ColorLookup.TRACK)
    assert isinstance(effect, expected_cls)
    assert not hasattr(effect, "color")
    assert not hasattr(effect, "color_lookup")


def test_detection_style_map_covers_every_enum_member():
    # the builder map and the DetectionStyle enum stay in lock-step (sync-by-proximity)
    assert set(annotators._DETECTION_STYLES) == set(DetectionStyle)
