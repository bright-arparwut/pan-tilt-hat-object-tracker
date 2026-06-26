"""Unit tests for the CLI seam: argument parsing, validation, and class resolution.

Covers the pure CLI seams — no YOLO/video required:
- ``build_parser`` parsing of ``--zoom-max`` / ``--track*`` / ``--zoom-track-id``,
- ``validation_error`` for zoom and track arg combinations,
- ``_resolve_classes`` (general by default; ``--classes 14`` reproduces bird-only).
"""

from __future__ import annotations

import pytest

from object_tracker.cli import _resolve_classes, build_parser, validation_error
from object_tracker.config import (
    COCO_BIRD_CLASS_ID,
    DEFAULT_TRACK_ACTIVATION,
    DEFAULT_TRACK_BUFFER,
)


# --- CLI: zoom-max -----------------------------------------------------------------
def test_zoom_max_defaults_to_one():
    args = build_parser().parse_args(["--source", "x.mp4"])
    assert args.zoom_max == 1


def test_zoom_max_parses_explicit_value():
    args = build_parser().parse_args(["--source", "x.mp4", "--zoom-max", "6"])
    assert args.zoom_max == 6


# --- CLI: track flags --------------------------------------------------------------
def test_track_defaults_on():
    args = build_parser().parse_args(["--source", "x.mp4"])
    assert args.track is True


def test_no_track_flag_disables_tracking():
    args = build_parser().parse_args(["--source", "x.mp4", "--no-track"])
    assert args.track is False


def test_track_buffer_and_activation_parse():
    args = build_parser().parse_args(
        ["--source", "x.mp4", "--track-buffer", "50", "--track-activation", "0.4"]
    )
    assert args.track_buffer == 50
    assert args.track_activation == 0.4


def test_track_knob_defaults():
    args = build_parser().parse_args(["--source", "x.mp4"])
    assert args.track_buffer == DEFAULT_TRACK_BUFFER
    assert args.track_activation == DEFAULT_TRACK_ACTIVATION


def test_zoom_track_id_defaults_none_and_parses():
    assert build_parser().parse_args(["--source", "x.mp4"]).zoom_track_id is None
    args = build_parser().parse_args(["--source", "x.mp4", "--zoom-track-id", "7"])
    assert args.zoom_track_id == 7


# --- validation: zoom --------------------------------------------------------------
@pytest.mark.parametrize("zoom_max", [0, -1])
def test_validation_rejects_non_positive_zoom_max(zoom_max):
    err = validation_error(zoom_size=0.05, zoom_max=zoom_max)
    assert err is not None and "zoom-max" in err


def test_validation_accepts_valid_args():
    assert validation_error(zoom_size=0.05, zoom_max=1) is None


def test_validation_still_rejects_bad_zoom_size():
    assert validation_error(zoom_size=0.0, zoom_max=1) is not None


# --- validation: track -------------------------------------------------------------
def test_validation_accepts_valid_track_args():
    assert (
        validation_error(
            zoom_size=0.05,
            zoom_max=1,
            track=True,
            track_buffer=30,
            track_activation=0.25,
            zoom_track_id=None,
        )
        is None
    )


@pytest.mark.parametrize("buffer", [0, -5])
def test_validation_rejects_non_positive_track_buffer(buffer):
    err = validation_error(zoom_size=0.05, zoom_max=1, track_buffer=buffer)
    assert err is not None and "track-buffer" in err


@pytest.mark.parametrize("activation", [0.0, -0.1, 1.5])
def test_validation_rejects_out_of_range_track_activation(activation):
    err = validation_error(zoom_size=0.05, zoom_max=1, track_activation=activation)
    assert err is not None and "track-activation" in err


def test_validation_rejects_zoom_track_id_without_track():
    err = validation_error(zoom_size=0.05, zoom_max=1, track=False, zoom_track_id=7)
    assert err is not None and "zoom-track-id" in err


def test_validation_accepts_zoom_track_id_with_track():
    assert (
        validation_error(zoom_size=0.05, zoom_max=1, track=True, zoom_track_id=7)
        is None
    )


# --- class resolution (general by default; ADR-0008) -------------------------------
def test_resolve_classes_defaults_to_all_classes_on_stock_weights():
    # ADR-0008: no --classes -> all classes, independent of stock vs custom weights.
    args = build_parser().parse_args(["--source", "x.mp4"])
    assert _resolve_classes(args) is None


def test_resolve_classes_explicit_classes_detect_any_object():
    args = build_parser().parse_args(["--source", "x.mp4", "--classes", "0", "16"])
    assert _resolve_classes(args) == (0, 16)


def test_resolve_classes_classes_14_reproduces_bird_only():
    # The old bird default is now explicit: --classes 14 == bird-only.
    args = build_parser().parse_args(
        ["--source", "x.mp4", "--classes", str(COCO_BIRD_CLASS_ID)]
    )
    assert _resolve_classes(args) == (COCO_BIRD_CLASS_ID,)
