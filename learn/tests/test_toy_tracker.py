"""Week 5 acceptance: your own tracker. Sandbox-only — no counterpart in the reference repo."""

from __future__ import annotations

import numpy as np
import pytest
import supervision as sv

from object_tracker.toy_tracker import ToyTrackerState, iou_matrix, update


def _dets(*boxes):
    return sv.Detections(
        xyxy=np.asarray(boxes, dtype=float),
        confidence=np.asarray([0.9] * len(boxes), dtype=float),
        class_id=np.asarray([0] * len(boxes)),
    )


def test_iou_of_identical_boxes_is_one():
    box = np.asarray([[0.0, 0.0, 10.0, 10.0]])
    assert iou_matrix(box, box)[0, 0] == pytest.approx(1.0)


def test_iou_of_disjoint_boxes_is_zero():
    a = np.asarray([[0.0, 0.0, 10.0, 10.0]])
    b = np.asarray([[50.0, 50.0, 60.0, 60.0]])
    assert iou_matrix(a, b)[0, 0] == pytest.approx(0.0)


def test_a_track_keeps_its_id_while_it_keeps_matching():
    state = ToyTrackerState()
    out, state = update(state, _dets([0, 0, 10, 10]), frame_idx=0)
    first_id = int(out.tracker_id[0])

    # The object drifts a little each frame — IoU stays well above threshold.
    for frame_idx in range(1, 5):
        shift = frame_idx
        out, state = update(state, _dets([shift, 0, 10 + shift, 10]), frame_idx=frame_idx)
        assert int(out.tracker_id[0]) == first_id


def test_an_unmatched_track_survives_one_miss_then_dies():
    """A detector blinks. An object behind a lamp post is still the same object."""
    state = ToyTrackerState()
    _, state = update(state, _dets([0, 0, 10, 10]), frame_idx=0, max_age=2)

    _, state = update(state, _dets(), frame_idx=1, max_age=2)
    assert len(state.tracks) == 1, "one miss must not kill a track"

    _, state = update(state, _dets(), frame_idx=4, max_age=2)
    assert len(state.tracks) == 0, "past max_age the track is gone"
