"""Week 6 acceptance: the confirmed-Track view."""

from __future__ import annotations

import numpy as np
import supervision as sv

from object_tracker.tracking import _annotate_confirmed, _build_track_annotators, _present_centers


def test_present_centers_returns_python_floats_not_numpy():
    """These centres reach json.dumps on the turret wire in week 11.

    A numpy float32 raises "not JSON serializable" there — crashing a control loop with a
    motor moving. Fix it at the source, here.
    """
    confirmed = sv.Detections(
        xyxy=np.asarray([[0.0, 0.0, 10.0, 20.0]], dtype=np.float32),
        confidence=np.asarray([0.9], dtype=np.float32),
        class_id=np.asarray([0]),
        tracker_id=np.asarray([3]),
    )
    centers = _present_centers(confirmed)
    assert centers == {3: (5.0, 10.0)}
    cx, cy = centers[3]
    assert type(cx) is float and type(cy) is float, "numpy float32 must not escape this function"


def test_annotate_confirmed_is_a_noop_without_tracker_ids():
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    ann = _build_track_annotators((64, 48))
    out = _annotate_confirmed(frame, sv.Detections.empty(), ann)
    assert np.array_equal(out, frame)
    assert out is not frame, "annotate on a copy — never mutate the caller's frame"
