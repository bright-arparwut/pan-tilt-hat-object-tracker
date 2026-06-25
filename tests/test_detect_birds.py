"""Unit tests for the configurable multi-bird Zoom Inset (issue 07).

Covers the pure seams: top-N centre selection, the right-edge panel strip renderer,
CLI parsing of ``--zoom-max``, and argument validation. No YOLO/video required.
"""

from __future__ import annotations

import numpy as np
import pytest
import supervision as sv

import detect_birds as db

GREEN = db.ZOOM_BORDER_BGR  # (0, 255, 0)


def _dets(boxes, confs):
    return sv.Detections(
        xyxy=np.asarray(boxes, dtype=float),
        confidence=np.asarray(confs, dtype=float),
        class_id=np.asarray([db.COCO_BIRD_CLASS_ID] * len(confs)),
    )


# --- top_centers -------------------------------------------------------------------
def test_top_centers_empty_detections_returns_empty():
    assert db.top_centers(sv.Detections.empty(), 5) == []


def test_top_centers_without_confidence_returns_empty():
    dets = sv.Detections(xyxy=np.array([[0, 0, 10, 10]], dtype=float))
    assert db.top_centers(dets, 3) == []


def test_top_centers_orders_by_confidence_descending():
    # box centres: A=(5,5) conf .4, B=(30,30) conf .9, C=(105,105) conf .6
    dets = _dets([[0, 0, 10, 10], [20, 20, 40, 40], [100, 100, 110, 110]], [0.4, 0.9, 0.6])
    centers = db.top_centers(dets, 3)
    assert centers == [(30.0, 30.0), (105.0, 105.0), (5.0, 5.0)]


def test_top_centers_caps_at_n():
    dets = _dets([[0, 0, 10, 10], [20, 20, 40, 40], [100, 100, 110, 110]], [0.4, 0.9, 0.6])
    centers = db.top_centers(dets, 2)
    assert centers == [(30.0, 30.0), (105.0, 105.0)]


def test_top_centers_n_larger_than_available_returns_all():
    dets = _dets([[0, 0, 10, 10], [20, 20, 40, 40]], [0.4, 0.9])
    assert len(db.top_centers(dets, 10)) == 2


# --- draw_zoom_panels --------------------------------------------------------------
FRAME_WH = (200, 100)  # (w, h)


def _gray_source():
    return np.full((FRAME_WH[1], FRAME_WH[0], 3), 128, dtype=np.uint8)


def test_draw_zoom_panels_empty_centers_leaves_canvas_untouched():
    canvas = np.zeros((FRAME_WH[1], FRAME_WH[0], 3), dtype=np.uint8)
    out = db.draw_zoom_panels(canvas, _gray_source(), [], 0.05, FRAME_WH, zoom_max=4)
    assert np.array_equal(out, np.zeros_like(out))


def test_draw_zoom_panels_single_matches_legacy_top_right_panel():
    # zoom_max=1 -> panel = min(0.25*200, 100) = 50, drawn top-right.
    canvas = np.zeros((FRAME_WH[1], FRAME_WH[0], 3), dtype=np.uint8)
    db.draw_zoom_panels(canvas, _gray_source(), [(100.0, 50.0)], 0.05, FRAME_WH, zoom_max=1)
    # interior of the panel carries the (gray) crop content
    assert tuple(canvas[25, 175]) == (128, 128, 128)
    # a green border pixel exists along the panel's left edge
    assert (canvas[:50, 150] == GREEN).all(axis=1).any()
    # nothing drawn outside the panel
    assert (canvas[25, 100] == 0).all()


def test_draw_zoom_panels_stacks_multiple_down_right_edge():
    # zoom_max=2 -> panel = min(50, 100//2=50) = 50, two stacked slots.
    canvas = np.zeros((FRAME_WH[1], FRAME_WH[0], 3), dtype=np.uint8)
    db.draw_zoom_panels(
        canvas, _gray_source(), [(100.0, 50.0), (40.0, 40.0)], 0.05, FRAME_WH, zoom_max=2
    )
    assert tuple(canvas[25, 175]) == (128, 128, 128)  # slot 0
    assert tuple(canvas[75, 175]) == (128, 128, 128)  # slot 1


def test_draw_zoom_panels_draws_fewer_than_capacity_leaving_rest_blank():
    # zoom_max=4 -> panel = min(50, 100//4=25) = 25; only 2 centres -> slots 2,3 blank.
    canvas = np.zeros((FRAME_WH[1], FRAME_WH[0], 3), dtype=np.uint8)
    db.draw_zoom_panels(
        canvas, _gray_source(), [(100.0, 50.0), (40.0, 40.0)], 0.05, FRAME_WH, zoom_max=4
    )
    assert tuple(canvas[12, 187]) == (128, 128, 128)  # slot 0 interior
    assert tuple(canvas[37, 187]) == (128, 128, 128)  # slot 1 interior
    # slots 2 and 3 are never drawn -> their interiors stay blank (no crop content)
    assert tuple(canvas[62, 187]) == (0, 0, 0)  # slot 2 interior
    assert tuple(canvas[87, 187]) == (0, 0, 0)  # slot 3 interior


# --- CLI ---------------------------------------------------------------------------
def test_zoom_max_defaults_to_one():
    args = db.build_parser().parse_args(["--source", "x.mp4"])
    assert args.zoom_max == 1


def test_zoom_max_parses_explicit_value():
    args = db.build_parser().parse_args(["--source", "x.mp4", "--zoom-max", "6"])
    assert args.zoom_max == 6


# --- validation --------------------------------------------------------------------
@pytest.mark.parametrize("zoom_max", [0, -1])
def test_validation_rejects_non_positive_zoom_max(zoom_max):
    err = db.validation_error(zoom_size=0.05, zoom_max=zoom_max)
    assert err is not None and "zoom-max" in err


def test_validation_accepts_valid_args():
    assert db.validation_error(zoom_size=0.05, zoom_max=1) is None


def test_validation_still_rejects_bad_zoom_size():
    assert db.validation_error(zoom_size=0.0, zoom_max=1) is not None
