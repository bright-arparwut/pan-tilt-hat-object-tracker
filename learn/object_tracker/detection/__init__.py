"""Detection package — the backend-agnostic Detector / TrackingDetector seams (ADR-0009/0012).

``build_detector(cfg, track)`` builds the YOLO backend (bound to the chosen Tracker) and
wraps it in ``SlicedDetector`` only on the non-tracking path. The pipeline depends only on
the Protocols exported here, never on a concrete model.
"""

from __future__ import annotations

import math

from ..config import MIN_SLICE_PX, DetectConfig, TrackConfig
from .base import Detector, TrackingDetector
from .yolo import SlicedDetector, YoloDetector

__all__ = [
    "Detector",
    "TrackingDetector",
    "YoloDetector",
    "SlicedDetector",
    "build_detector",
    "slice_warnings",
]


def _overlap_px(
    slice_wh: tuple[int, int], overlap_ratio_wh: tuple[float, float]
) -> tuple[int, int]:
    """Absolute per-axis overlap in px — the resolution-relative ratio × the tile side.

    supervision's ``InferenceSlicer`` takes absolute overlap; we expose a ratio so the same
    flags scale from a test clip to 4K (ADR-0002).
    """
    raise NotImplementedError("Week 4 — see learn/curriculum/week-04-sliced-inference.md")


def slice_warnings(
    slice_wh: tuple[int, int],
    overlap_ratio_wh: tuple[float, float],
    frame_wh: tuple[int, int],
) -> list[str]:
    """User-facing warnings for a degenerate ``--slice-wh`` on this frame (a guardrail).

    The slicer's merge is correct; these are *parameter* pathologies it cannot fix — so warn
    loudly rather than silently doing something useless or slow. Two arms:

    1. **Tile >= frame** → slicing yields one tile and does nothing at all.
    2. **Tile far smaller than the frame** (below ``MIN_SLICE_PX``) → many forward passes per
       frame (slow), heavy upscale (small objects vanish — the exact thing slicing was for),
       and objects larger than a tile fragment into overlapping boxes.

    Return ``[]`` for a sane subdividing tile, so a legitimate 4K run stays quiet. Include
    the computed tile count in the second message — a number is more persuasive than an
    adjective.

    This is **guardrails, not limits**: warn, then do what the user asked.
    """
    raise NotImplementedError("Week 4 — see learn/curriculum/week-04-sliced-inference.md")


def build_detector(cfg: DetectConfig, track: TrackConfig) -> Detector:
    """Build the YOLO backend; wrap it in ``SlicedDetector`` iff slicing is on **and**
    tracking is off.

    Under ``--track`` the backend runs ``model.track()`` directly, which sliced inference
    cannot host (ADR-0012), so the tracking path is **never** wrapped — and the returned
    backend is a ``TrackingDetector`` the pipeline calls ``track()`` on.

    Week 2: return the bare backend. Week 4: add the slicing branch. Week 6: add the tracking
    guard.
    """
    raise NotImplementedError("Week 2 — see learn/curriculum/week-02-detection.md")
