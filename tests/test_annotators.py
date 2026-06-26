"""Unit tests for the themed annotator factory (ADR-0011).

Covers ``build_box`` / ``build_label`` / ``build_trace_annotator``: that the defaults
reproduce the prior (un-themed) construction — the byte-identical invariant — and that the
Appearance knobs (scale multipliers, ``color_lookup`` / label-colour overrides) take effect.
The knobs are monkeypatched on the ``annotators`` module, where the builders read them.
"""

from __future__ import annotations

import supervision as sv

from object_tracker import annotators
from object_tracker.annotators import (
    build_box_annotator,
    build_label_annotator,
    build_trace_annotator,
)

FRAME_WH = (1920, 1080)  # (w, h)


# --- defaults reproduce the prior construction (byte-identical invariant) ----------
def test_box_defaults_match_optimal_thickness_and_class_lookup():
    box = build_box_annotator(FRAME_WH)
    assert box.thickness == sv.calculate_optimal_line_thickness(resolution_wh=FRAME_WH)
    assert box.color_lookup == sv.ColorLookup.CLASS
    assert box.color == sv.ColorPalette.DEFAULT


def test_box_honours_explicit_color_lookup():
    box = build_box_annotator(FRAME_WH, sv.ColorLookup.TRACK)
    assert box.color_lookup == sv.ColorLookup.TRACK


def test_label_defaults_match_optimal_scale_position_and_kept_text_color():
    thickness = sv.calculate_optimal_line_thickness(resolution_wh=FRAME_WH)
    label = build_label_annotator(FRAME_WH)
    assert label.text_scale == sv.calculate_optimal_text_scale(resolution_wh=FRAME_WH)
    assert label.text_thickness == max(1, thickness - 1)
    assert label.text_anchor == sv.Position.TOP_LEFT
    assert label.color_lookup == sv.ColorLookup.CLASS
    # LABEL_TEXT_COLOR is None by default -> supervision's white is kept, not overridden
    assert label.text_color == sv.Color.WHITE


def test_trace_defaults_carry_trace_length_and_center_anchor():
    trace = build_trace_annotator(FRAME_WH)
    assert trace.trace.max_size == annotators.TRACE_LENGTH  # 30 by default
    assert trace.trace.anchor == sv.Position.CENTER
    assert trace.thickness == sv.calculate_optimal_line_thickness(resolution_wh=FRAME_WH)
    assert trace.color_lookup == sv.ColorLookup.CLASS


# --- the Appearance knobs take effect ----------------------------------------------
def test_thickness_scale_multiplies_optimal_thickness(monkeypatch):
    base = sv.calculate_optimal_line_thickness(resolution_wh=FRAME_WH)
    monkeypatch.setattr(annotators, "THICKNESS_SCALE", 3.0)
    assert build_box_annotator(FRAME_WH).thickness == max(1, round(base * 3.0))


def test_text_scale_mult_multiplies_optimal_scale(monkeypatch):
    base = sv.calculate_optimal_text_scale(resolution_wh=FRAME_WH)
    monkeypatch.setattr(annotators, "TEXT_SCALE_MULT", 2.0)
    assert build_label_annotator(FRAME_WH).text_scale == base * 2.0


def test_color_lookup_override_beats_default_and_explicit_caller_lookup(monkeypatch):
    monkeypatch.setattr(annotators, "COLOR_LOOKUP_OVERRIDE", sv.ColorLookup.INDEX)
    assert build_box_annotator(FRAME_WH).color_lookup == sv.ColorLookup.INDEX
    forced = build_box_annotator(FRAME_WH, sv.ColorLookup.TRACK)
    assert forced.color_lookup == sv.ColorLookup.INDEX


def test_label_text_color_override_sets_text_color(monkeypatch):
    monkeypatch.setattr(annotators, "LABEL_TEXT_COLOR", sv.Color.RED)
    assert build_label_annotator(FRAME_WH).text_color == sv.Color.RED


def test_trace_length_override_sets_buffer_size(monkeypatch):
    monkeypatch.setattr(annotators, "TRACE_LENGTH", 7)
    assert build_trace_annotator(FRAME_WH).trace.max_size == 7
