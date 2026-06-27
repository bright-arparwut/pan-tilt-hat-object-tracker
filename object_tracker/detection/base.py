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
    """Given one frame, return that frame's identity-free Detections."""

    def detect(self, frame: np.ndarray) -> sv.Detections: ...


class TrackingDetector(Protocol):
    """Given one frame, return that frame's Detections carrying ``tracker_id`` (ADR-0012).

    The tracking counterpart of ``Detector``: ``detect`` is identity-free, ``track`` assigns
    identities (the backend runs Ultralytics ``model.track()`` internally). The pipeline
    depends on this when ``--track`` is on; the YOLO backend implements both.
    """

    def track(self, frame: np.ndarray) -> sv.Detections: ...
