"""Shared test fixtures for the object_tracker suite."""

from __future__ import annotations

import numpy as np
import pytest
import supervision as sv

from object_tracker.config import COCO_BIRD_CLASS_ID


@pytest.fixture
def dets():
    """Factory: build an ``sv.Detections`` from boxes + confidences (bird class)."""

    def _make(boxes, confs):
        return sv.Detections(
            xyxy=np.asarray(boxes, dtype=float),
            confidence=np.asarray(confs, dtype=float),
            class_id=np.asarray([COCO_BIRD_CLASS_ID] * len(confs)),
        )

    return _make
