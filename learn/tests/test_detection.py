"""Weeks 2, 4, 6 acceptance: the Detector seam, slicing, and the tracking branch."""

from __future__ import annotations

import numpy as np
import pytest
import supervision as sv

from object_tracker.config import DetectConfig, TrackConfig, TrackerKind
from object_tracker.detection import build_detector, slice_warnings
from object_tracker.detection.yolo import SlicedDetector, YoloDetector
from object_tracker.device import resolve_device


class _FakeResult:
    boxes = None


class _FakeModel:
    """Records what it was called with. No weights, no GPU — that is the point."""

    def __init__(self):
        self.predict_kwargs = []
        self.track_kwargs = []

    def __call__(self, frame, **kwargs):
        self.predict_kwargs.append(kwargs)
        return [_FakeResult()]

    def predict(self, frame, **kwargs):
        return self(frame, **kwargs)

    def track(self, frame, **kwargs):
        self.track_kwargs.append(kwargs)
        return [_FakeResult()]


# --- week 2 -------------------------------------------------------------------------
def test_yolo_detector_passes_conf_and_classes_to_the_model(monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr("object_tracker.detection.yolo.YOLO", lambda *a, **k: fake)
    monkeypatch.setattr(sv.Detections, "from_ultralytics", staticmethod(lambda r: sv.Detections.empty()))

    detector = YoloDetector("w.pt", conf=0.4, classes=(14,), device="cpu")
    detector.detect(np.zeros((48, 64, 3), dtype=np.uint8))

    assert fake.predict_kwargs, "the backend must actually call the model"
    kwargs = fake.predict_kwargs[-1]
    assert kwargs["conf"] == 0.4
    assert tuple(kwargs["classes"]) == (14,)


def test_yolo_detector_returns_sv_detections(monkeypatch):
    monkeypatch.setattr("object_tracker.detection.yolo.YOLO", lambda *a, **k: _FakeModel())
    monkeypatch.setattr(sv.Detections, "from_ultralytics", staticmethod(lambda r: sv.Detections.empty()))

    detector = YoloDetector("w.pt", conf=0.15, classes=None, device="cpu")
    out = detector.detect(np.zeros((48, 64, 3), dtype=np.uint8))
    assert isinstance(out, sv.Detections)


def test_resolve_device_prefers_available_accelerator():
    assert resolve_device("cpu") == "cpu"          # explicit always wins
    assert resolve_device("cuda:0") == "cuda:0"
    assert resolve_device(None) in {"cpu", "mps", "cuda"}


# --- week 4 -------------------------------------------------------------------------
def test_sliced_detector_calls_the_wrapped_detector_per_tile():
    calls = []

    class _CountingDetector:
        def detect(self, frame):
            calls.append(frame.shape)
            return sv.Detections.empty()

    sliced = SlicedDetector(_CountingDetector(), (64, 64), (12, 12), "nms", 1)
    sliced.detect(np.zeros((256, 256, 3), dtype=np.uint8))

    assert len(calls) > 1, "a 256x256 frame with 64x64 tiles must produce many forward passes"


def test_slice_warnings_flags_a_tile_larger_than_the_frame():
    warnings = slice_warnings((640, 640), (0.2, 0.2), (480, 320))
    assert len(warnings) == 1
    assert "no effect" in warnings[0] or "one tile" in warnings[0]


def test_slice_warnings_is_silent_for_a_sane_subdividing_tile():
    assert slice_warnings((640, 640), (0.2, 0.2), (3840, 2160)) == []


# --- week 6 -------------------------------------------------------------------------
def test_build_detector_never_wraps_the_tracking_path_in_the_slicer(monkeypatch):
    """model.track() runs the model directly, so there is no seam for the slicer (ADR-0012)."""
    monkeypatch.setattr("object_tracker.detection.yolo.YOLO", lambda *a, **k: _FakeModel())
    cfg = DetectConfig(
        weights="w.pt", conf=0.15, classes=None, device="cpu",
        use_slicing=True, slice_wh=(640, 640), overlap_ratio_wh=(0.2, 0.2),
        overlap_filter="nms", thread_workers=1,
    )
    tracking = TrackConfig(enabled=True, tracker=TrackerKind.BYTETRACK, buffer=60)
    assert not isinstance(build_detector(cfg, tracking), SlicedDetector)

    plain = TrackConfig(enabled=False, tracker=TrackerKind.BYTETRACK, buffer=60)
    assert isinstance(build_detector(cfg, plain), SlicedDetector)
