"""Unit tests for the in-loop tracking id-join mechanism.

Covers the pure seams — no YOLO/video required:
- ``_build_track_map`` raw-row -> track_id join via the stashed ``_idx``,
- ``_present_centers`` tracker_id -> box centre.
"""

from __future__ import annotations

import numpy as np
import supervision as sv

from object_tracker.config import COCO_BIRD_CLASS_ID
from object_tracker.tracking import _build_track_map, _present_centers


# --- _build_track_map / _present_centers (the id-join mechanism) -------------------
def _confirmed(idx, tracker_ids, boxes):
    """A confirmed sv.Detections as update_with_detections returns it (carries _idx)."""
    return sv.Detections(
        xyxy=np.asarray(boxes, dtype=float),
        class_id=np.asarray([COCO_BIRD_CLASS_ID] * len(boxes)),
        tracker_id=np.asarray(tracker_ids),
        data={"_idx": np.asarray(idx)},
    )


def test_build_track_map_uses_stashed_idx_for_raw_row_join():
    # ByteTrack kept rows 0 and 2 (ids 5, 6) and dropped the noise row 1.
    confirmed = _confirmed([0, 2], [5, 6], [[0, 0, 10, 10], [100, 100, 110, 110]])
    assert _build_track_map(confirmed) == {0: 5, 2: 6}


def test_build_track_map_empty_when_no_confirmed_tracks():
    assert _build_track_map(sv.Detections.empty()) == {}


def test_present_centers_maps_tracker_id_to_box_centre():
    confirmed = _confirmed([0, 1], [5, 6], [[0, 0, 10, 20], [20, 20, 40, 60]])
    assert _present_centers(confirmed) == {5: (5.0, 10.0), 6: (30.0, 40.0)}


def test_present_centers_empty_when_no_tracks():
    assert _present_centers(sv.Detections.empty()) == {}
