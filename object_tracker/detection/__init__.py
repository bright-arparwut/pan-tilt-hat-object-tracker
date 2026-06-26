"""Detection package — the backend-agnostic Detector seam (ADR-0009).

``build_detector(cfg)`` builds the configured backend and wraps it in ``SlicedDetector``
iff slicing is on. The pipeline depends only on the ``Detector`` Protocol exported here,
never on a concrete model.
"""

from __future__ import annotations

from ..config import DetectConfig
from .base import Detector
from .yolo import SlicedDetector, YoloDetector

__all__ = ["Detector", "YoloDetector", "SlicedDetector", "build_detector"]


def build_detector(cfg: DetectConfig) -> Detector:
    """Build the backend; wrap it in ``SlicedDetector`` iff ``cfg.use_slicing``."""
    base: Detector = YoloDetector(cfg.weights, cfg.conf, cfg.classes, cfg.device)
    if not cfg.use_slicing:
        return base
    # supervision takes absolute overlap in px; we expose a resolution-relative ratio.
    overlap_wh = (
        int(cfg.overlap_ratio_wh[0] * cfg.slice_wh[0]),
        int(cfg.overlap_ratio_wh[1] * cfg.slice_wh[1]),
    )
    return SlicedDetector(
        base, cfg.slice_wh, overlap_wh, cfg.overlap_filter, cfg.thread_workers
    )
