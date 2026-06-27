"""Unit tests for the detections sidecar serialisation (``detection_records``).

Covers the schema: legacy (``--no-track``) byte-for-byte, and the ``--track`` path reading
``tracker_id`` straight off the detections (ids pre-attached by model.track(); ADR-0012).
No YOLO/video required.
"""

from __future__ import annotations

import numpy as np
import supervision as sv

from object_tracker.config import COCO_BIRD_CLASS_ID
from object_tracker.sidecar import detection_records, frame_record


def _tracked(boxes, confs, tracker_ids):
    """An sv.Detections carrying tracker_id, as model.track() -> from_ultralytics yields."""
    return sv.Detections(
        xyxy=np.asarray(boxes, dtype=float),
        confidence=np.asarray(confs, dtype=float),
        class_id=np.asarray([COCO_BIRD_CLASS_ID] * len(confs)),
        tracker_id=np.asarray(tracker_ids) if tracker_ids is not None else None,
    )


# --- detection_records schema ------------------------------------------------------
def test_detection_records_without_track_id_keeps_legacy_schema(dets):
    # --no-track must stay byte-for-byte today's schema: exactly these keys, in order.
    d = dets([[0, 0, 10, 10], [20, 20, 40, 40]], [0.9, 0.16])
    records = detection_records(d)
    assert all(list(r.keys()) == ["xyxy", "conf", "cls", "name"] for r in records)


def test_detection_records_reads_tracker_id_per_row():
    # Under --track every returned row carries its id (model.track output; ADR-0012).
    d = _tracked(
        [[0, 0, 10, 10], [20, 20, 40, 40], [100, 100, 110, 110]],
        [0.9, 0.8, 0.7],
        [5, 6, 7],
    )
    records = detection_records(d, with_track_id=True)
    assert [r["track_id"] for r in records] == [5, 6, 7]


def test_detection_records_null_track_id_when_frame_has_no_ids():
    # A frame model.track() returns without ids -> track_id present but null on every row.
    d = _tracked([[0, 0, 10, 10]], [0.16], None)
    records = detection_records(d, with_track_id=True)
    assert records[0]["track_id"] is None
    assert "track_id" in records[0]


def test_detection_records_track_id_is_plain_int_not_numpy():
    # from_ultralytics hands np.int64 ids; the sidecar must serialise plain ints for JSON.
    d = _tracked([[0, 0, 10, 10]], [0.9], [np.int64(3)])
    rec = detection_records(d, with_track_id=True)[0]
    assert rec["track_id"] == 3 and type(rec["track_id"]) is int


# --- frame_record schema (Offline byte-identical; Live carries a capture ts) --------
def test_frame_record_offline_omits_ts_byte_identical():
    # ts=None (Offline) must stay exactly today's schema: {"frame", "detections"} in order.
    record = frame_record(7, [{"xyxy": [0, 0, 1, 1]}])
    assert record == {"frame": 7, "detections": [{"xyxy": [0, 0, 1, 1]}]}
    assert list(record.keys()) == ["frame", "detections"]


def test_frame_record_live_inserts_ts_between_frame_and_detections():
    record = frame_record(3, [], ts=1234.5)
    assert record == {"frame": 3, "ts": 1234.5, "detections": []}
    assert list(record.keys()) == ["frame", "ts", "detections"]
