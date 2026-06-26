"""Tests for source classification + the Live ``CameraSource`` (ADR-0010).

``classify_source`` is pure (no IO) and table-tested. ``CameraSource`` is exercised over a
**fake** ``cv2.VideoCapture`` — no real camera or network — to check frame iteration, the
fps fallback, the unbounded ``VideoInfo``, and the clear error on an un-openable device.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from object_tracker import sources
from object_tracker.config import DEFAULT_CAMERA_FPS
from object_tracker.sources import CameraSource, CameraSpec, FileSpec, classify_source


def _frames(n: int, w: int = 64, h: int = 48) -> list[np.ndarray]:
    return [np.full((h, w, 3), i, dtype=np.uint8) for i in range(n)]


# --- classify_source (pure) --------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("0", CameraSpec(0)),
        ("12", CameraSpec(12)),
        ("rtsp://cam/stream", CameraSpec("rtsp://cam/stream")),
        ("http://cam/feed.mjpg", CameraSpec("http://cam/feed.mjpg")),
        ("https://cam/feed", CameraSpec("https://cam/feed")),
        ("udp://239.0.0.1:1234", CameraSpec("udp://239.0.0.1:1234")),
        ("tcp://cam:5000", CameraSpec("tcp://cam:5000")),
    ],
)
def test_classify_source_returns_camera_spec_for_digits_and_urls(text, expected):
    assert classify_source(text) == expected


@pytest.mark.parametrize("text", ["clip.mp4", "./a/b.mov", "/abs/path.mkv", "footage/x.mp4"])
def test_classify_source_returns_file_spec_for_paths(text):
    spec = classify_source(text)
    assert isinstance(spec, FileSpec)
    assert spec.path == Path(text)


# --- CameraSource over a fake VideoCapture -----------------------------------------


class FakeCapture:
    """Stand-in for ``cv2.VideoCapture`` — serves queued frames, then EOF."""

    def __init__(self, frames, *, opened=True, fps=30.0, w=64, h=48):
        self._frames = list(frames)
        self._opened = opened
        self._fps = fps
        self._w = w
        self._h = h
        self.released = False

    def isOpened(self):
        return self._opened

    def get(self, prop):
        import cv2

        return {
            cv2.CAP_PROP_FRAME_WIDTH: float(self._w),
            cv2.CAP_PROP_FRAME_HEIGHT: float(self._h),
            cv2.CAP_PROP_FPS: float(self._fps),
        }[prop]

    def read(self):
        if self._frames:
            return True, self._frames.pop(0)
        return False, None

    def release(self):
        self.released = True


def _patch(monkeypatch, fake):
    monkeypatch.setattr(sources.cv2, "VideoCapture", lambda target: fake)


def test_camera_source_yields_every_queued_frame_then_stops(monkeypatch):
    frames = _frames(3)
    fake = FakeCapture(frames)
    _patch(monkeypatch, fake)

    src = CameraSource(CameraSpec(0))
    out = list(src)

    assert len(out) == 3
    for got, want in zip(out, frames):
        assert got is want
    assert src.info.total_frames is None
    src.release()
    assert fake.released is True


def test_camera_source_derives_resolution(monkeypatch):
    _patch(monkeypatch, FakeCapture(_frames(1), w=128, h=72))
    src = CameraSource(CameraSpec(0))
    assert src.info.resolution_wh == (128, 72)


def test_camera_source_uses_reported_fps_when_positive(monkeypatch):
    _patch(monkeypatch, FakeCapture(_frames(1), fps=24.0))
    src = CameraSource(CameraSpec(0))
    assert src.info.fps == 24


def test_camera_source_falls_back_to_default_fps_when_zero(monkeypatch):
    _patch(monkeypatch, FakeCapture(_frames(1), fps=0.0))
    src = CameraSource(CameraSpec(0))
    assert src.info.fps == DEFAULT_CAMERA_FPS


def test_camera_source_raises_clear_error_when_not_opened(monkeypatch):
    _patch(monkeypatch, FakeCapture([], opened=False))
    with pytest.raises(RuntimeError, match="could not open"):
        CameraSource(CameraSpec(0))


def test_camera_source_accepts_stream_url(monkeypatch):
    captured = {}

    def fake_video_capture(target):
        captured["target"] = target
        return FakeCapture(_frames(1))

    monkeypatch.setattr(sources.cv2, "VideoCapture", fake_video_capture)
    CameraSource(CameraSpec("rtsp://cam/stream"))
    assert captured["target"] == "rtsp://cam/stream"
