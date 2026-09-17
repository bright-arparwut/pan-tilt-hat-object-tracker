"""Week 3 acceptance: the machine-facing detections record."""

from __future__ import annotations

import json

import numpy as np
import supervision as sv

from object_tracker.sidecar import detection_records, frame_record


def test_frame_record_offline_schema_has_no_ts():
    record = frame_record(7, [{"xyxy": [0, 0, 1, 1]}])
    assert list(record.keys()) == ["frame", "detections"]
    assert record["frame"] == 7


def test_frame_record_live_inserts_ts_between_frame_and_detections():
    record = frame_record(7, [], ts=1234.5)
    assert list(record.keys()) == ["frame", "ts", "detections"]


def test_detection_records_round_trips_xyxy_conf_and_class():
    detections = sv.Detections(
        xyxy=np.asarray([[10.04, 20.06, 30.0, 40.0]], dtype=np.float32),
        confidence=np.asarray([0.87654], dtype=np.float32),
        class_id=np.asarray([14]),
    )
    rows = detection_records(detections)
    assert rows == [{"xyxy": [10.0, 20.1, 30.0, 40.0], "conf": 0.8765, "cls": 14, "name": None}]
    assert "track_id" not in rows[0], "the --no-track schema omits the key entirely"
    json.dumps(rows)  # must not raise: every value is a plain Python type, not numpy
