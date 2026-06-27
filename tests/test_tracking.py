"""Unit tests for the track-view helpers (ADR-0012).

Covers the pure seam — no YOLO/video required: ``_present_centers`` maps each confirmed
Track's ``tracker_id`` to its box centre (the input the identity-mode zoom slots consume).
Identities now arrive pre-attached from ``model.track()``; there is no in-loop id-join.
"""

from __future__ import annotations

import numpy as np
import supervision as sv

from object_tracker.config import COCO_BIRD_CLASS_ID
from object_tracker.tracking import _present_centers


def _confirmed(tracker_ids, boxes):
    """A confirmed sv.Detections as model.track() -> from_ultralytics returns it."""
    return sv.Detections(
        xyxy=np.asarray(boxes, dtype=float),
        class_id=np.asarray([COCO_BIRD_CLASS_ID] * len(boxes)),
        tracker_id=np.asarray(tracker_ids),
    )


def test_present_centers_maps_tracker_id_to_box_centre():
    confirmed = _confirmed([5, 6], [[0, 0, 10, 20], [20, 20, 40, 60]])
    assert _present_centers(confirmed) == {5: (5.0, 10.0), 6: (30.0, 40.0)}


def test_present_centers_empty_when_no_tracks():
    assert _present_centers(sv.Detections.empty()) == {}
