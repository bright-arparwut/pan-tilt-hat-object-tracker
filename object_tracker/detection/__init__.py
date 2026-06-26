"""Detection package — the backend-agnostic Detector / TrackingDetector seams (ADR-0009/0012).

``build_detector(cfg, track)`` builds the YOLO backend (bound to the chosen Tracker) and
wraps it in ``SlicedDetector`` only on the non-tracking path. The pipeline depends only on
the Protocols exported here, never on a concrete model.
"""

from __future__ import annotations

from ..config import DetectConfig, TrackConfig
from .base import Detector, TrackingDetector
from .yolo import SlicedDetector, YoloDetector

__all__ = [
    "Detector",
    "TrackingDetector",
    "YoloDetector",
    "SlicedDetector",
    "build_detector",
]


def build_detector(cfg: DetectConfig, track: TrackConfig) -> Detector:
    """Build the YOLO backend; wrap it in ``SlicedDetector`` iff slicing is on **and**
    tracking is off.

    Under ``--track`` the backend runs ``model.track()`` directly, which sliced inference
    can't host (ADR-0012), so the tracking path is never wrapped — and the returned backend
    is a ``TrackingDetector`` the pipeline calls ``track()`` on.
    """
    base: Detector = YoloDetector(
        cfg.weights, cfg.conf, cfg.classes, cfg.device, track.tracker.value
    )
    if track.enabled or not cfg.use_slicing:
        return base
    # supervision takes absolute overlap in px; we expose a resolution-relative ratio.
    overlap_wh = (
        int(cfg.overlap_ratio_wh[0] * cfg.slice_wh[0]),
        int(cfg.overlap_ratio_wh[1] * cfg.slice_wh[1]),
    )
    return SlicedDetector(
        base, cfg.slice_wh, overlap_wh, cfg.overlap_filter, cfg.thread_workers
    )
