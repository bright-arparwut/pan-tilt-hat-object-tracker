"""Unit tests for the Detector seam: SlicedDetector decorator + build_detector factory.

Proves backend-agnosticism — a fake non-YOLO Detector is wrapped and driven by
``SlicedDetector`` with no ultralytics import — and the factory's slicing toggle. The
live YOLO equivalence is covered by the end-to-end smoke run.
"""

from __future__ import annotations

import numpy as np
import supervision as sv

import object_tracker.detection as detection
from object_tracker.config import MIN_SLICE_PX, DetectConfig, TrackConfig, TrackerKind
from object_tracker.detection import SlicedDetector, build_detector, slice_warnings


class _FakeDetector:
    """Backend-agnostic stub: counts calls, returns a fixed per-slice Detections.

    Accepts the ``YoloDetector(weights, conf, classes, device)`` signature so it can stand
    in for the backend under ``build_detector`` without importing ultralytics.
    """

    def __init__(self, *args, per_slice: sv.Detections | None = None, **kwargs) -> None:
        self.calls = 0
        self._per_slice = per_slice

    def detect(self, frame: np.ndarray) -> sv.Detections:
        self.calls += 1
        if self._per_slice is None:
            return sv.Detections.empty()
        return self._per_slice


def _cfg(**over) -> DetectConfig:
    base = dict(
        weights="yolo11n.pt",
        conf=0.15,
        classes=(14,),
        device="cpu",
        use_slicing=True,
        slice_wh=(64, 64),
        overlap_ratio_wh=(0.0, 0.0),
        overlap_filter="nms",
        thread_workers=1,
    )
    base.update(over)
    return DetectConfig(**base)  # type: ignore[arg-type]


def _track(enabled: bool) -> TrackConfig:
    return TrackConfig(enabled=enabled, tracker=TrackerKind.BYTETRACK, buffer=30)


# --- SlicedDetector over a fake Detector (backend-agnostic) ------------------------
def test_sliced_detector_single_slice_passes_base_detections_through():
    # slice_wh == frame size with zero overlap -> one slice at origin -> no offset.
    known = sv.Detections(
        xyxy=np.array([[1.0, 1.0, 5.0, 5.0]]),
        confidence=np.array([0.9]),
        class_id=np.array([0]),
    )
    base = _FakeDetector(per_slice=known)
    sliced = SlicedDetector(base, (64, 64), (0, 0), "nms", 1)
    out = sliced.detect(np.zeros((64, 64, 3), dtype=np.uint8))
    assert base.calls == 1
    assert np.allclose(out.xyxy, known.xyxy)


def test_sliced_detector_calls_base_once_per_slice():
    # 128x64 frame, 64x64 slices, no overlap -> 2 slices -> base.detect called twice.
    base = _FakeDetector()  # returns empty per slice
    sliced = SlicedDetector(base, (64, 64), (0, 0), "nms", 1)
    sliced.detect(np.zeros((64, 128, 3), dtype=np.uint8))
    assert base.calls == 2


# --- build_detector slicing toggle -------------------------------------------------
def test_build_detector_no_slice_returns_bare_backend(monkeypatch):
    monkeypatch.setattr(detection, "YoloDetector", _FakeDetector)
    d = build_detector(_cfg(use_slicing=False), _track(enabled=False))
    assert isinstance(d, _FakeDetector)


def test_build_detector_slice_wraps_in_sliced_detector(monkeypatch):
    monkeypatch.setattr(detection, "YoloDetector", _FakeDetector)
    d = build_detector(_cfg(use_slicing=True), _track(enabled=False))
    assert isinstance(d, SlicedDetector)


def test_build_detector_track_skips_slicer_even_when_slice_on(monkeypatch):
    # Tracking runs model.track() directly; sliced inference can't host it (ADR-0012),
    # so --track returns the bare tracking-capable backend even with --slice on.
    monkeypatch.setattr(detection, "YoloDetector", _FakeDetector)
    d = build_detector(_cfg(use_slicing=True), _track(enabled=True))
    assert isinstance(d, _FakeDetector)


# --- slice_warnings guardrails (pure; no model/video) ------------------------------
def test_slice_warnings_flags_tile_at_least_frame_size_as_noop():
    # Default 640x640 tile on a <=640px frame -> one tile -> slicing does nothing (ADR-0002).
    msgs = slice_warnings((640, 640), (0.2, 0.2), (640, 360))
    assert len(msgs) == 1
    assert "no effect" in msgs[0] and "--no-slice" in msgs[0]


def test_slice_warnings_flags_tiny_tile_with_estimated_tile_count():
    # 100px tile, 20% overlap -> 80px stride -> ceil(640/80)*ceil(360/80) = 8*5 = 40 tiles.
    msgs = slice_warnings((100, 100), (0.2, 0.2), (640, 360))
    assert len(msgs) == 1
    assert "~40 tiles" in msgs[0] and "fragment" in msgs[0]
    assert f">= {MIN_SLICE_PX}px" in msgs[0]


def test_slice_warnings_silent_for_sane_subdividing_tile():
    # 320px tile actually subdivides a 640x360 frame and stays well above the px floor.
    assert slice_warnings((320, 320), (0.2, 0.2), (640, 360)) == []


def test_slice_warnings_silent_for_640_tile_on_4k_frame():
    # The documented 4K use: 640 tiles subdivide a 3840x2160 frame — not a warning.
    assert slice_warnings((640, 640), (0.2, 0.2), (3840, 2160)) == []
