"""Unit tests for the Zoom Inset: confidence-mode strip + identity-pinned slots.

Covers the pure rendering/selection seams — no YOLO/video required:
- ``top_centers`` top-N centre selection,
- ``draw_zoom_panels`` right-edge panel strip,
- ``ZoomSlots`` slot lifecycle (first-seen fill, cap, black-through-buffer, snap-back,
  free-after-buffer with fixed position, ``--zoom-track-id`` single-slot lock),
- ``draw_identity_panels`` rendering (crop slot, black slot, vertical slot position).
"""

from __future__ import annotations

import numpy as np
import supervision as sv

from object_tracker.config import ZOOM_BORDER_BGR
from object_tracker.zoom import (
    SlotRender,
    ZoomSlots,
    draw_identity_panels,
    draw_zoom_panels,
    top_centers,
)

GREEN = ZOOM_BORDER_BGR  # (0, 255, 0)


# --- top_centers -------------------------------------------------------------------
def test_top_centers_empty_detections_returns_empty():
    assert top_centers(sv.Detections.empty(), 5) == []


def test_top_centers_without_confidence_returns_empty():
    dets = sv.Detections(xyxy=np.array([[0, 0, 10, 10]], dtype=float))
    assert top_centers(dets, 3) == []


def test_top_centers_orders_by_confidence_descending(dets):
    # box centres: A=(5,5) conf .4, B=(30,30) conf .9, C=(105,105) conf .6
    d = dets([[0, 0, 10, 10], [20, 20, 40, 40], [100, 100, 110, 110]], [0.4, 0.9, 0.6])
    centers = top_centers(d, 3)
    assert centers == [(30.0, 30.0), (105.0, 105.0), (5.0, 5.0)]


def test_top_centers_caps_at_n(dets):
    d = dets([[0, 0, 10, 10], [20, 20, 40, 40], [100, 100, 110, 110]], [0.4, 0.9, 0.6])
    centers = top_centers(d, 2)
    assert centers == [(30.0, 30.0), (105.0, 105.0)]


def test_top_centers_n_larger_than_available_returns_all(dets):
    d = dets([[0, 0, 10, 10], [20, 20, 40, 40]], [0.4, 0.9])
    assert len(top_centers(d, 10)) == 2


# --- draw_zoom_panels --------------------------------------------------------------
FRAME_WH = (200, 100)  # (w, h)


def _gray_source():
    return np.full((FRAME_WH[1], FRAME_WH[0], 3), 128, dtype=np.uint8)


def test_draw_zoom_panels_empty_centers_leaves_canvas_untouched():
    canvas = np.zeros((FRAME_WH[1], FRAME_WH[0], 3), dtype=np.uint8)
    out = draw_zoom_panels(canvas, _gray_source(), [], 0.05, FRAME_WH, zoom_max=4)
    assert np.array_equal(out, np.zeros_like(out))


def test_draw_zoom_panels_single_matches_legacy_top_right_panel():
    # zoom_max=1 -> panel = min(0.25*200, 100) = 50, drawn top-right.
    canvas = np.zeros((FRAME_WH[1], FRAME_WH[0], 3), dtype=np.uint8)
    draw_zoom_panels(canvas, _gray_source(), [(100.0, 50.0)], 0.05, FRAME_WH, zoom_max=1)
    # interior of the panel carries the (gray) crop content
    assert tuple(canvas[25, 175]) == (128, 128, 128)
    # a green border pixel exists along the panel's left edge
    assert (canvas[:50, 150] == GREEN).all(axis=1).any()
    # nothing drawn outside the panel
    assert (canvas[25, 100] == 0).all()


def test_draw_zoom_panels_stacks_multiple_down_right_edge():
    # zoom_max=2 -> panel = min(50, 100//2=50) = 50, two stacked slots.
    canvas = np.zeros((FRAME_WH[1], FRAME_WH[0], 3), dtype=np.uint8)
    draw_zoom_panels(
        canvas, _gray_source(), [(100.0, 50.0), (40.0, 40.0)], 0.05, FRAME_WH, zoom_max=2
    )
    assert tuple(canvas[25, 175]) == (128, 128, 128)  # slot 0
    assert tuple(canvas[75, 175]) == (128, 128, 128)  # slot 1


def test_draw_zoom_panels_draws_fewer_than_capacity_leaving_rest_blank():
    # zoom_max=4 -> panel = min(50, 100//4=25) = 25; only 2 centres -> slots 2,3 blank.
    canvas = np.zeros((FRAME_WH[1], FRAME_WH[0], 3), dtype=np.uint8)
    draw_zoom_panels(
        canvas, _gray_source(), [(100.0, 50.0), (40.0, 40.0)], 0.05, FRAME_WH, zoom_max=4
    )
    assert tuple(canvas[12, 187]) == (128, 128, 128)  # slot 0 interior
    assert tuple(canvas[37, 187]) == (128, 128, 128)  # slot 1 interior
    # slots 2 and 3 are never drawn -> their interiors stay blank (no crop content)
    assert tuple(canvas[62, 187]) == (0, 0, 0)  # slot 2 interior
    assert tuple(canvas[87, 187]) == (0, 0, 0)  # slot 3 interior


# --- ZoomSlots lifecycle -----------------------------------------------------------
def _ids_by_index(renders):
    return {r.index: r.track_id for r in renders}


def test_slots_fill_first_seen_order_and_cap():
    slots = ZoomSlots(max_slots=2, buffer=3)
    slots.update({1: (10, 10)}, 0)
    slots.update({1: (10, 10), 2: (20, 20)}, 1)
    renders = slots.update({1: (10, 10), 2: (20, 20), 3: (30, 30)}, 2)
    # id 3 gets no slot (cap 2); slots 0,1 keep ids 1,2 in first-seen order
    assert _ids_by_index(renders) == {0: 1, 1: 2}


def test_slot_present_id_has_center_first_bind_snaps_to_target():
    slots = ZoomSlots(max_slots=1, buffer=3)
    renders = slots.update({1: (10.0, 20.0)}, 0)
    assert len(renders) == 1
    assert renders[0].track_id == 1
    assert renders[0].center == (10.0, 20.0)  # first bind snaps (no EMA from nothing)


def test_slot_goes_black_while_lost_within_buffer_then_snaps_back():
    slots = ZoomSlots(max_slots=1, buffer=3)
    slots.update({1: (10, 10)}, 0)
    r1 = slots.update({}, 1)  # gap 1 -> black, slot held
    r2 = slots.update({}, 2)  # gap 2 -> black, slot held
    assert r1[0].track_id == 1 and r1[0].center is None
    assert r2[0].track_id == 1 and r2[0].center is None
    r3 = slots.update({1: (50.0, 60.0)}, 3)  # gap 3 <= buffer -> snap back, same slot
    assert r3[0].index == 0 and r3[0].track_id == 1 and r3[0].center == (50.0, 60.0)


def test_slot_freed_after_buffer_and_reused_at_same_index_by_new_id():
    slots = ZoomSlots(max_slots=2, buffer=2)
    slots.update({1: (10, 10), 2: (20, 20)}, 0)  # slot0->1, slot1->2
    slots.update({2: (20, 20)}, 1)  # slot0 black (gap1), slot1 present
    slots.update({2: (20, 20)}, 2)  # slot0 black (gap2 <= buffer)
    renders = slots.update({2: (20, 20), 3: (30, 30)}, 3)  # gap3 > buffer -> free slot0
    # freed slot 0 is reused by the new id 3; slot 1 keeps id 2 (no reflow)
    assert _ids_by_index(renders) == {0: 3, 1: 2}


def test_zoom_track_id_locks_single_slot_and_ignores_others():
    slots = ZoomSlots(max_slots=5, buffer=3, forced_id=7)
    assert slots.update({1: (10, 10), 2: (20, 20)}, 0) == []  # 7 absent -> nothing
    r = slots.update({1: (10, 10), 7: (70.0, 80.0)}, 1)  # 7 appears -> single slot
    assert len(r) == 1 and r[0].track_id == 7 and r[0].center == (70.0, 80.0)
    r2 = slots.update({1: (10, 10)}, 2)  # 7 missing -> black, still single slot
    assert len(r2) == 1 and r2[0].track_id == 7 and r2[0].center is None


# --- draw_identity_panels ----------------------------------------------------------
def test_draw_identity_panels_empty_leaves_canvas_untouched():
    canvas = np.zeros((FRAME_WH[1], FRAME_WH[0], 3), dtype=np.uint8)
    out = draw_identity_panels(canvas, _gray_source(), [], 0.05, FRAME_WH, max_slots=2)
    assert np.array_equal(out, np.zeros_like(out))


def test_draw_identity_panels_crop_slot_carries_source_content():
    # max_slots=2 -> panel = min(0.25*200, 100//2) = 50, slot 0 at top.
    canvas = np.zeros((FRAME_WH[1], FRAME_WH[0], 3), dtype=np.uint8)
    renders = [SlotRender(index=0, track_id=1, center=(100.0, 50.0))]
    draw_identity_panels(canvas, _gray_source(), renders, 0.05, FRAME_WH, max_slots=2)
    assert tuple(canvas[40, 185]) == (128, 128, 128)  # crop content, below the label


def test_draw_identity_panels_black_slot_is_black_with_border_and_label():
    canvas = np.full((FRAME_WH[1], FRAME_WH[0], 3), 50, dtype=np.uint8)  # non-black bg
    renders = [SlotRender(index=1, track_id=9, center=None)]  # slot 1 -> top=50
    draw_identity_panels(canvas, _gray_source(), renders, 0.05, FRAME_WH, max_slots=2)
    # panel interior (away from any label) is black
    assert tuple(canvas[75, 175]) == (0, 0, 0)
    # green border on the panel's left edge within its vertical band
    assert (canvas[50:100, 150] == GREEN).all(axis=1).any()
    # a green label glyph is drawn inside the (black) panel near the top-left
    assert (canvas[51:70, 151:198] == GREEN).all(axis=2).any()


def test_draw_identity_panels_slot_index_sets_vertical_position():
    canvas = np.zeros((FRAME_WH[1], FRAME_WH[0], 3), dtype=np.uint8)
    renders = [SlotRender(index=1, track_id=2, center=(100.0, 50.0))]
    draw_identity_panels(canvas, _gray_source(), renders, 0.05, FRAME_WH, max_slots=2)
    # slot 1 occupies rows 50..99; slot 0 band stays blank
    assert tuple(canvas[75, 185]) == (128, 128, 128)  # slot 1 crop content
    assert tuple(canvas[25, 185]) == (0, 0, 0)  # slot 0 untouched
