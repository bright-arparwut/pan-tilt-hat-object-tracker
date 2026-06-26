"""YOLO detection backend + the backend-agnostic sliced-inference decorator.

``YoloDetector`` is a ``Detector`` Backend wrapping one ``YOLO`` model (owning its conf,
class filter, and device). ``SlicedDetector`` is a ``Detector`` *decorator* that runs any
base ``Detector`` over slices via ``supervision``'s ``InferenceSlicer`` — backend-agnostic,
revising ADR-0003's slicing-on-the-YOLO-path assumption. Both return ``sv.Detections``.
"""

from __future__ import annotations

import numpy as np
import supervision as sv
from ultralytics import YOLO

from .base import Detector


def _overlap_filter(name: str) -> sv.OverlapFilter:
    if name == "nmm":
        return sv.OverlapFilter.NON_MAX_MERGE
    return sv.OverlapFilter.NON_MAX_SUPPRESSION


class YoloDetector:
    """A Detector Backend: one ``YOLO`` model with its conf / class filter / device."""

    def __init__(
        self,
        weights: str,
        conf: float,
        classes: tuple[int, ...] | None,
        device: str,
    ) -> None:
        self._model = YOLO(weights)
        self._conf = conf
        self._classes = list(classes) if classes else None
        self._device = device

    def detect(self, frame: np.ndarray) -> sv.Detections:
        result = self._model(
            frame,
            conf=self._conf,
            classes=self._classes,
            device=self._device,
            verbose=False,
        )[0]
        return sv.Detections.from_ultralytics(result)


class SlicedDetector:
    """A Detector decorator: run a base Detector over slices (ADR-0003, any backend).

    Slicing stays a runtime toggle (ADR-0002) and resolution-agnostic — the caller passes
    absolute ``overlap_wh`` in px (derived from the resolution-relative ratio by the
    factory). Returns merged ``sv.Detections`` so nothing downstream branches on slicing.
    """

    def __init__(
        self,
        base: Detector,
        slice_wh: tuple[int, int],
        overlap_wh: tuple[int, int],
        overlap_filter: str,
        thread_workers: int,
    ) -> None:
        self._slicer = sv.InferenceSlicer(
            callback=base.detect,
            slice_wh=slice_wh,
            overlap_wh=overlap_wh,
            overlap_filter=_overlap_filter(overlap_filter),
            thread_workers=thread_workers,
        )

    def detect(self, frame: np.ndarray) -> sv.Detections:
        return self._slicer(frame)
