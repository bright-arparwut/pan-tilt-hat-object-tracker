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
    return (
        round(overlap_ratio_wh[0] * slice_wh[0]),
        round(overlap_ratio_wh[1] * slice_wh[1]),
    )


def slice_warnings(
    slice_wh: tuple[int, int],
    overlap_ratio_wh: tuple[float, float],
    frame_wh: tuple[int, int],
) -> list[str]:
    """User-facing warnings for a degenerate ``--slice-wh`` on this frame (a guardrail).

    The slicer merge is correct; these are *parameter* pathologies it can't fix. A tile
    ``>=`` the frame makes slicing a no-op (ADR-0002 — slicing targets larger/4K frames). A
    tile far smaller than the frame is slow (many forward passes), drops small objects (heavy
    upscale), and fragments objects larger than the tile into overlapping boxes. Returns
    ``[]`` for a sane subdividing tile, so a legitimate 4K run stays quiet.
    """
    fw, fh = frame_wh
    sw, sh = slice_wh
    if sw >= fw and sh >= fh:
        return [
            f"--slice-wh {sw}x{sh} >= frame {fw}x{fh}: slicing yields one tile (no effect). "
            f"Slicing targets larger frames (ADR-0002) — use --no-slice on small clips."
        ]
    if min(sw, sh) < MIN_SLICE_PX:
        ow, oh = _overlap_px(slice_wh, overlap_ratio_wh)
        tiles = math.ceil(fw / max(1, sw - ow)) * math.ceil(fh / max(1, sh - oh))
        return [
            f"--slice-wh {sw}x{sh} is small for a {fw}x{fh} frame (~{tiles} tiles/frame): "
            f"slow, tiny tiles drop small objects (heavy upscale), and objects larger than "
            f"{sw}x{sh}px fragment into overlapping boxes. Raise --slice-wh (>= {MIN_SLICE_PX}px) "
            f"or use --no-slice."
        ]
    return []


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
    overlap_wh = _overlap_px(cfg.slice_wh, cfg.overlap_ratio_wh)
    return SlicedDetector(
        base, cfg.slice_wh, overlap_wh, cfg.overlap_filter, cfg.thread_workers
    )
