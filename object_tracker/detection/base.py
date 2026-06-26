"""The backend-agnostic Detector seam (ADR-0009).

The pipeline depends only on this Protocol — never on a concrete model — so a future
DETR / RF-DETR backend slots in without touching the loop. Every backend (and the
``SlicedDetector`` decorator) returns ``sv.Detections``, the ADR-0002/0003 invariant.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
import supervision as sv


class Detector(Protocol):
    """Given one frame, return that frame's Detections."""

    def detect(self, frame: np.ndarray) -> sv.Detections: ...
