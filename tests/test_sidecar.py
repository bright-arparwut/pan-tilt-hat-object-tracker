"""Unit tests for the detections sidecar serialisation (``detection_records``).

Covers the id-join: raw rows preserved, nullable ``track_id``, legacy schema under
``--no-track``, and plain-int serialisation. No YOLO/video required.
"""

from __future__ import annotations

import numpy as np

from object_tracker.sidecar import detection_records


# --- detection_records id-join -----------------------------------------------------
def test_detection_records_without_track_map_keeps_legacy_schema(dets):
    # --no-track must stay byte-for-byte today's schema: exactly these keys, in order.
    d = dets([[0, 0, 10, 10], [20, 20, 40, 40]], [0.9, 0.16])
    records = detection_records(d)
    assert all(list(r.keys()) == ["xyxy", "conf", "cls", "name"] for r in records)


def test_detection_records_joins_track_id_per_raw_row(dets):
    # rows 0 and 2 belong to confirmed tracks; row 1 is recall-first noise -> null
    d = dets(
        [[0, 0, 10, 10], [20, 20, 40, 40], [100, 100, 110, 110]], [0.9, 0.16, 0.8]
    )
    records = detection_records(d, {0: 5, 2: 6})
    assert [r["track_id"] for r in records] == [5, None, 6]


def test_detection_records_empty_track_map_marks_all_rows_null(dets):
    d = dets([[0, 0, 10, 10]], [0.16])
    records = detection_records(d, {})
    assert records[0]["track_id"] is None
    assert "track_id" in records[0]


def test_detection_records_track_id_is_plain_int_not_numpy(dets):
    d = dets([[0, 0, 10, 10]], [0.9])
    # ByteTrack hands np.int64 ids; the sidecar must serialise plain ints for JSON.
    rec = detection_records(d, {0: np.int64(3)})[0]  # pyright: ignore[reportArgumentType]
    assert rec["track_id"] == 3 and type(rec["track_id"]) is int
