"""Unit tests for in-loop tracking + identity-mode Zoom Inset (issue 08).

Covers the pure seams only — no YOLO/video required:
- ``detection_records`` id-join (raw rows preserved, nullable ``track_id``),
- ``validation_error`` for the new track flags,
- CLI parsing of ``--track`` / ``--track-buffer`` / ``--track-activation`` / ``--zoom-track-id``,
- ``ZoomSlots`` slot lifecycle (first-seen fill, cap, black-through-buffer, snap-back,
  free-after-buffer with fixed position, ``--zoom-track-id`` single-slot lock),
- ``draw_identity_panels`` rendering (crop slot, black slot, vertical slot position).
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


# --- detection_records id-join -----------------------------------------------------
def test_detection_records_without_track_map_keeps_legacy_schema():
    # --no-track must stay byte-for-byte today's schema: exactly these keys, in order.
    dets = _dets([[0, 0, 10, 10], [20, 20, 40, 40]], [0.9, 0.16])
    records = db.detection_records(dets)
    assert all(list(r.keys()) == ["xyxy", "conf", "cls", "name"] for r in records)


def test_detection_records_joins_track_id_per_raw_row():
    # rows 0 and 2 belong to confirmed tracks; row 1 is recall-first noise -> null
    dets = _dets(
        [[0, 0, 10, 10], [20, 20, 40, 40], [100, 100, 110, 110]], [0.9, 0.16, 0.8]
    )
    records = db.detection_records(dets, {0: 5, 2: 6})
    assert [r["track_id"] for r in records] == [5, None, 6]


def test_detection_records_empty_track_map_marks_all_rows_null():
    dets = _dets([[0, 0, 10, 10]], [0.16])
    records = db.detection_records(dets, {})
    assert records[0]["track_id"] is None
    assert "track_id" in records[0]


def test_detection_records_track_id_is_plain_int_not_numpy():
    dets = _dets([[0, 0, 10, 10]], [0.9])
    # ByteTrack hands np.int64 ids; the sidecar must serialise plain ints for JSON.
    rec = db.detection_records(dets, {0: np.int64(3)})[0]  # pyright: ignore[reportArgumentType]
    assert rec["track_id"] == 3 and type(rec["track_id"]) is int


# --- _build_track_map / _present_centers (the id-join mechanism) -------------------
def _confirmed(idx, tracker_ids, boxes):
    """A confirmed sv.Detections as update_with_detections returns it (carries _idx)."""
    return sv.Detections(
        xyxy=np.asarray(boxes, dtype=float),
        class_id=np.asarray([db.COCO_BIRD_CLASS_ID] * len(boxes)),
        tracker_id=np.asarray(tracker_ids),
        data={"_idx": np.asarray(idx)},
    )


def test_build_track_map_uses_stashed_idx_for_raw_row_join():
    # ByteTrack kept rows 0 and 2 (ids 5, 6) and dropped the noise row 1.
    confirmed = _confirmed([0, 2], [5, 6], [[0, 0, 10, 10], [100, 100, 110, 110]])
    assert db._build_track_map(confirmed) == {0: 5, 2: 6}


def test_build_track_map_empty_when_no_confirmed_tracks():
    assert db._build_track_map(sv.Detections.empty()) == {}


def test_present_centers_maps_tracker_id_to_box_centre():
    confirmed = _confirmed([0, 1], [5, 6], [[0, 0, 10, 20], [20, 20, 40, 60]])
    assert db._present_centers(confirmed) == {5: (5.0, 10.0), 6: (30.0, 40.0)}


def test_present_centers_empty_when_no_tracks():
    assert db._present_centers(sv.Detections.empty()) == {}


# --- validation_error --------------------------------------------------------------
def test_validation_accepts_valid_track_args():
    assert (
        db.validation_error(
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
    err = db.validation_error(zoom_size=0.05, zoom_max=1, track_buffer=buffer)
    assert err is not None and "track-buffer" in err


@pytest.mark.parametrize("activation", [0.0, -0.1, 1.5])
def test_validation_rejects_out_of_range_track_activation(activation):
    err = db.validation_error(zoom_size=0.05, zoom_max=1, track_activation=activation)
    assert err is not None and "track-activation" in err


def test_validation_rejects_zoom_track_id_without_track():
    err = db.validation_error(zoom_size=0.05, zoom_max=1, track=False, zoom_track_id=7)
    assert err is not None and "zoom-track-id" in err


def test_validation_accepts_zoom_track_id_with_track():
    assert (
        db.validation_error(zoom_size=0.05, zoom_max=1, track=True, zoom_track_id=7)
        is None
    )


# --- CLI ---------------------------------------------------------------------------
def test_track_defaults_on():
    args = db.build_parser().parse_args(["--source", "x.mp4"])
    assert args.track is True


def test_no_track_flag_disables_tracking():
    args = db.build_parser().parse_args(["--source", "x.mp4", "--no-track"])
    assert args.track is False


def test_track_buffer_and_activation_parse():
    args = db.build_parser().parse_args(
        ["--source", "x.mp4", "--track-buffer", "50", "--track-activation", "0.4"]
    )
    assert args.track_buffer == 50
    assert args.track_activation == 0.4


def test_track_knob_defaults():
    args = db.build_parser().parse_args(["--source", "x.mp4"])
    assert args.track_buffer == db.DEFAULT_TRACK_BUFFER
    assert args.track_activation == db.DEFAULT_TRACK_ACTIVATION


def test_zoom_track_id_defaults_none_and_parses():
    assert db.build_parser().parse_args(["--source", "x.mp4"]).zoom_track_id is None
    args = db.build_parser().parse_args(["--source", "x.mp4", "--zoom-track-id", "7"])
    assert args.zoom_track_id == 7


# --- ZoomSlots lifecycle -----------------------------------------------------------
def _ids_by_index(renders):
    return {r.index: r.track_id for r in renders}


def test_slots_fill_first_seen_order_and_cap():
    slots = db.ZoomSlots(max_slots=2, buffer=3)
    slots.update({1: (10, 10)}, 0)
    slots.update({1: (10, 10), 2: (20, 20)}, 1)
    renders = slots.update({1: (10, 10), 2: (20, 20), 3: (30, 30)}, 2)
    # id 3 gets no slot (cap 2); slots 0,1 keep ids 1,2 in first-seen order
    assert _ids_by_index(renders) == {0: 1, 1: 2}


def test_slot_present_id_has_center_first_bind_snaps_to_target():
    slots = db.ZoomSlots(max_slots=1, buffer=3)
    renders = slots.update({1: (10.0, 20.0)}, 0)
    assert len(renders) == 1
    assert renders[0].track_id == 1
    assert renders[0].center == (10.0, 20.0)  # first bind snaps (no EMA from nothing)


def test_slot_goes_black_while_lost_within_buffer_then_snaps_back():
    slots = db.ZoomSlots(max_slots=1, buffer=3)
    slots.update({1: (10, 10)}, 0)
    r1 = slots.update({}, 1)  # gap 1 -> black, slot held
    r2 = slots.update({}, 2)  # gap 2 -> black, slot held
    assert r1[0].track_id == 1 and r1[0].center is None
    assert r2[0].track_id == 1 and r2[0].center is None
    r3 = slots.update({1: (50.0, 60.0)}, 3)  # gap 3 <= buffer -> snap back, same slot
    assert r3[0].index == 0 and r3[0].track_id == 1 and r3[0].center == (50.0, 60.0)


def test_slot_freed_after_buffer_and_reused_at_same_index_by_new_id():
    slots = db.ZoomSlots(max_slots=2, buffer=2)
    slots.update({1: (10, 10), 2: (20, 20)}, 0)  # slot0->1, slot1->2
    slots.update({2: (20, 20)}, 1)  # slot0 black (gap1), slot1 present
    slots.update({2: (20, 20)}, 2)  # slot0 black (gap2 <= buffer)
    renders = slots.update({2: (20, 20), 3: (30, 30)}, 3)  # gap3 > buffer -> free slot0
    # freed slot 0 is reused by the new id 3; slot 1 keeps id 2 (no reflow)
    assert _ids_by_index(renders) == {0: 3, 1: 2}


def test_zoom_track_id_locks_single_slot_and_ignores_others():
    slots = db.ZoomSlots(max_slots=5, buffer=3, forced_id=7)
    assert slots.update({1: (10, 10), 2: (20, 20)}, 0) == []  # 7 absent -> nothing
    r = slots.update({1: (10, 10), 7: (70.0, 80.0)}, 1)  # 7 appears -> single slot
    assert len(r) == 1 and r[0].track_id == 7 and r[0].center == (70.0, 80.0)
    r2 = slots.update({1: (10, 10)}, 2)  # 7 missing -> black, still single slot
    assert len(r2) == 1 and r2[0].track_id == 7 and r2[0].center is None


# --- draw_identity_panels ----------------------------------------------------------
FRAME_WH = (200, 100)  # (w, h)


def _gray_source():
    return np.full((FRAME_WH[1], FRAME_WH[0], 3), 128, dtype=np.uint8)


def test_draw_identity_panels_empty_leaves_canvas_untouched():
    canvas = np.zeros((FRAME_WH[1], FRAME_WH[0], 3), dtype=np.uint8)
    out = db.draw_identity_panels(canvas, _gray_source(), [], 0.05, FRAME_WH, max_slots=2)
    assert np.array_equal(out, np.zeros_like(out))


def test_draw_identity_panels_crop_slot_carries_source_content():
    # max_slots=2 -> panel = min(0.25*200, 100//2) = 50, slot 0 at top.
    canvas = np.zeros((FRAME_WH[1], FRAME_WH[0], 3), dtype=np.uint8)
    renders = [db.SlotRender(index=0, track_id=1, center=(100.0, 50.0))]
    db.draw_identity_panels(canvas, _gray_source(), renders, 0.05, FRAME_WH, max_slots=2)
    assert tuple(canvas[40, 185]) == (128, 128, 128)  # crop content, below the label


def test_draw_identity_panels_black_slot_is_black_with_border_and_label():
    canvas = np.full((FRAME_WH[1], FRAME_WH[0], 3), 50, dtype=np.uint8)  # non-black bg
    renders = [db.SlotRender(index=1, track_id=9, center=None)]  # slot 1 -> top=50
    db.draw_identity_panels(canvas, _gray_source(), renders, 0.05, FRAME_WH, max_slots=2)
    # panel interior (away from any label) is black
    assert tuple(canvas[75, 175]) == (0, 0, 0)
    # green border on the panel's left edge within its vertical band
    assert (canvas[50:100, 150] == GREEN).all(axis=1).any()
    # a green label glyph is drawn inside the (black) panel near the top-left
    assert (canvas[51:70, 151:198] == GREEN).all(axis=2).any()


def test_draw_identity_panels_slot_index_sets_vertical_position():
    canvas = np.zeros((FRAME_WH[1], FRAME_WH[0], 3), dtype=np.uint8)
    renders = [db.SlotRender(index=1, track_id=2, center=(100.0, 50.0))]
    db.draw_identity_panels(canvas, _gray_source(), renders, 0.05, FRAME_WH, max_slots=2)
    # slot 1 occupies rows 50..99; slot 0 band stays blank
    assert tuple(canvas[75, 185]) == (128, 128, 128)  # slot 1 crop content
    assert tuple(canvas[25, 185]) == (0, 0, 0)  # slot 0 untouched
