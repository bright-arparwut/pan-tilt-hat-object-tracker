"""YOLO Detector Backend + the SlicedDetector decorator (ADR-0009/0012).

``YoloDetector`` owns exactly one model and answers two questions about a frame:
``detect()`` (identity-free, week 2) and ``track()`` (identities via ``model.track()``,
week 6). ``SlicedDetector`` (week 4) is a ``Detector`` that *wraps* a ``Detector`` and runs
it over the tiles of a frame — the decorator pattern over a Protocol, which is why a future
backend gets sliced inference for free.
"""

from __future__ import annotations

import numpy as np
import supervision as sv
from ultralytics import YOLO

from .base import Detector


class YoloDetector:
    """One Ultralytics model, wrapped to satisfy ``Detector`` (and ``TrackingDetector``).

    Load the weights **once** in ``__init__`` — not per frame. Own the confidence threshold,
    class filter and device here: how a backend honours those is its own business, and the
    pipeline must not need to know.
    """

    def __init__(
        self,
        weights: str,
        conf: float,
        classes: tuple[int, ...] | None,
        device: str,
        tracker: str = "bytetrack.yaml",
    ) -> None:
        raise NotImplementedError("Week 2 — see learn/curriculum/week-02-detection.md")

    def detect(self, frame: np.ndarray) -> sv.Detections:
        """One frame in, that frame's identity-free Detections out.

        ``classes=None`` means keep every class the weights know (ADR-0008, general by
        default) — not "keep nothing".
        """
        raise NotImplementedError("Week 2 — see learn/curriculum/week-02-detection.md")

    def track(self, frame: np.ndarray) -> sv.Detections:
        """One frame in, Detections carrying ``tracker_id`` out (ADR-0012).

        Runs ``model.track(frame, persist=True, tracker=...)``. ``persist=True`` is what
        tells Ultralytics these frames are one continuous sequence rather than unrelated
        images — drop it and every frame starts a fresh tracker. Try it once, to see.

        Thresholds are **not** set here: they live in the tracker's shipped yaml.
        """
        raise NotImplementedError("Week 6 — see learn/curriculum/week-06-bytetrack.md")


class SlicedDetector:
    """A ``Detector`` that runs another ``Detector`` over the Slices of a frame (ADR-0003).

    The SAHI *technique* as a decorator: it **is** a Detector and it **wraps** a Detector, so
    the pipeline cannot tell the difference and a future backend inherits slicing for nothing.

    Built on supervision's ``InferenceSlicer``, which takes **absolute** overlap in pixels —
    the caller converts from a resolution-relative ratio, so the same flags scale from a test
    clip to 4K.

    ``overlap_filter`` picks how per-slice results are merged: ``"nms"`` suppresses the
    lower-confidence duplicate, ``"nmm"`` merges the boxes. Think about which one an object
    fragmented across a tile boundary actually needs.
    """

    def __init__(
        self,
        base: Detector,
        slice_wh: tuple[int, int],
        overlap_wh: tuple[int, int],
        overlap_filter: str,
        thread_workers: int,
    ) -> None:
        raise NotImplementedError("Week 4 — see learn/curriculum/week-04-sliced-inference.md")

    def detect(self, frame: np.ndarray) -> sv.Detections:
        raise NotImplementedError("Week 4 — see learn/curriculum/week-04-sliced-inference.md")
