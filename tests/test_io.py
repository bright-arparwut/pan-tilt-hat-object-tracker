"""Tests for the FrameSource / FrameSink seams (ADR-0010).

The seams decouple ``pipeline.run`` from files at both ends. These tests drive ``run``
with a fake source + sink (no disk, no cv2, no YOLO) to prove the loop depends only on the
Protocols, and check the file-backed ``FileSource`` / ``VideoFileSink`` against fakes for
``supervision`` so no real video is needed.
"""

from __future__ import annotations

import json

import numpy as np
import pytest
import supervision as sv

from object_tracker.config import COCO_BIRD_CLASS_ID, TrackConfig, TrackerKind, ZoomConfig
from object_tracker.pipeline import run
from object_tracker.sinks import VideoFileSink
from object_tracker.sources import FileSource

# --- shared fakes ------------------------------------------------------------------


class StubDetector:
    """A ``Detector`` that returns no detections (keeps the loop branch-free)."""

    def detect(self, frame: np.ndarray) -> sv.Detections:
        return sv.Detections.empty()


class StubTrackingDetector:
    """A backend whose ``track()`` returns one detection with a fixed id; its ``detect`` must
    never be reached on the ``--track`` path (it asserts if it is)."""

    def detect(self, frame: np.ndarray) -> sv.Detections:
        raise AssertionError("the --track path must call track(), not detect()")

    def track(self, frame: np.ndarray) -> sv.Detections:
        return sv.Detections(
            xyxy=np.array([[0.0, 0.0, 10.0, 10.0]]),
            confidence=np.array([0.9]),
            class_id=np.array([COCO_BIRD_CLASS_ID]),
            tracker_id=np.array([7]),
        )


class FakeSource:
    """A ``FrameSource`` over an in-memory frame list + a hand-built ``VideoInfo``."""

    def __init__(self, frames: list[np.ndarray], info: sv.VideoInfo) -> None:
        self._frames = frames
        self.info = info
        self.released = 0

    def __iter__(self):
        return iter(self._frames)

    def release(self) -> None:
        self.released += 1


class RecordingSink:
    """A ``FrameSink`` that records shown frames + tracks; stops after ``stop_after`` shows."""

    def __init__(self, stop_after: int | None = None) -> None:
        self.shown: list[np.ndarray] = []
        self.shown_tracks: list = []
        self.closed = 0
        self._stop_after = stop_after

    def show(self, frame: np.ndarray, tracks=None) -> bool:
        self.shown.append(frame)
        self.shown_tracks.append(tracks)
        if self._stop_after is not None and len(self.shown) >= self._stop_after:
            return False
        return True

    def close(self) -> None:
        self.closed += 1


def _frames(n: int, w: int = 64, h: int = 48) -> list[np.ndarray]:
    return [np.zeros((h, w, 3), dtype=np.uint8) for _ in range(n)]


def _info(n: int | None, w: int = 64, h: int = 48) -> sv.VideoInfo:
    return sv.VideoInfo(width=w, height=h, fps=30, total_frames=n)


_NO_ZOOM = ZoomConfig(enabled=False, size=0.05, max_panels=1)
_NO_TRACK = TrackConfig(enabled=False, tracker=TrackerKind.BYTETRACK, buffer=30)
_TRACK = TrackConfig(enabled=True, tracker=TrackerKind.BYTETRACK, buffer=30)


# --- the seam: run() over fakes ----------------------------------------------------


def test_run_reads_every_frame_and_shows_every_annotated():
    source = FakeSource(_frames(3), _info(3))
    sink = RecordingSink()

    run(StubDetector(), source, sink, _NO_ZOOM, _NO_TRACK, sidecar_path=None)

    assert len(sink.shown) == 3
    assert sink.closed == 1
    assert source.released == 1


def test_run_stops_when_sink_returns_false():
    source = FakeSource(_frames(5), _info(5))
    sink = RecordingSink(stop_after=2)

    run(StubDetector(), source, sink, _NO_ZOOM, _NO_TRACK, sidecar_path=None)

    assert len(sink.shown) == 2  # stopped early, not all 5
    assert sink.closed == 1
    assert source.released == 1


def test_run_closes_sink_and_releases_source_even_on_detector_error():
    class Boom(StubDetector):
        def detect(self, frame):
            raise RuntimeError("detector blew up")

    source = FakeSource(_frames(3), _info(3))
    sink = RecordingSink()

    try:
        run(Boom(), source, sink, _NO_ZOOM, _NO_TRACK, sidecar_path=None)
    except RuntimeError:
        pass

    assert sink.closed == 1
    assert source.released == 1


def test_run_releases_and_closes_on_keyboard_interrupt():
    class Interrupting(StubDetector):
        def __init__(self):
            self.calls = 0

        def detect(self, frame):
            self.calls += 1
            if self.calls == 2:
                raise KeyboardInterrupt
            return sv.Detections.empty()

    source = FakeSource(_frames(5), _info(5))
    sink = RecordingSink()

    with pytest.raises(KeyboardInterrupt):
        run(Interrupting(), source, sink, _NO_ZOOM, _NO_TRACK, sidecar_path=None)

    assert sink.closed == 1  # cleanup ran on Ctrl-C
    assert source.released == 1


def test_run_writes_sidecar_when_path_given(tmp_path):
    side = tmp_path / "out" / "dets.jsonl"
    source = FakeSource(_frames(2), _info(2))

    run(StubDetector(), source, RecordingSink(), _NO_ZOOM, _NO_TRACK, sidecar_path=side)

    lines = side.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"frame": 0, "detections": []}
    assert json.loads(lines[1]) == {"frame": 1, "detections": []}


def test_run_writes_no_sidecar_when_path_is_none(tmp_path):
    source = FakeSource(_frames(2), _info(2))
    run(StubDetector(), source, RecordingSink(), _NO_ZOOM, _NO_TRACK, sidecar_path=None)
    assert list(tmp_path.iterdir()) == []  # nothing written


def test_run_track_path_calls_track_and_records_id(tmp_path):
    # --track: the loop drives detector.track() (not detect) and the sidecar carries the id.
    side = tmp_path / "tracked.jsonl"
    source = FakeSource(_frames(2), _info(2))

    run(StubTrackingDetector(), source, RecordingSink(), _NO_ZOOM, _TRACK, sidecar_path=side)

    rows = [json.loads(line) for line in side.read_text().splitlines()]
    assert len(rows) == 2
    assert [d["track_id"] for d in rows[0]["detections"]] == [7]


def test_run_track_path_passes_confirmed_tracks_to_sink():
    source = FakeSource(_frames(2), _info(2))
    sink = RecordingSink()

    run(StubTrackingDetector(), source, sink, _NO_ZOOM, _TRACK, sidecar_path=None)

    assert len(sink.shown_tracks) == 2
    for tracks in sink.shown_tracks:
        assert tracks is not None
        assert list(tracks.tracker_id) == [7]


def test_run_no_track_path_passes_none_tracks():
    source = FakeSource(_frames(2), _info(2))
    sink = RecordingSink()

    run(StubDetector(), source, sink, _NO_ZOOM, _NO_TRACK, sidecar_path=None)

    assert sink.shown_tracks == [None, None]


def test_run_live_sidecar_includes_capture_ts(tmp_path):
    side = tmp_path / "live.jsonl"
    source = FakeSource(_frames(2), _info(None))  # total_frames=None => Live (unbounded)

    run(StubDetector(), source, RecordingSink(), _NO_ZOOM, _NO_TRACK, sidecar_path=side)

    rows = [json.loads(line) for line in side.read_text().splitlines()]
    assert len(rows) == 2
    for i, row in enumerate(rows):
        assert row["frame"] == i
        assert isinstance(row["ts"], (int, float))  # capture timestamp present
        assert row["detections"] == []


# --- FileSource over a fake supervision backend ------------------------------------


def test_file_source_iterates_frames_and_exposes_info(monkeypatch, tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"not really a video")
    info = _info(4)
    queued = _frames(4)

    monkeypatch.setattr(
        sv.VideoInfo, "from_video_path", staticmethod(lambda p: info)
    )
    monkeypatch.setattr(
        "object_tracker.sources.sv.get_video_frames_generator",
        lambda p: iter(queued),
    )

    source = FileSource(clip)

    assert source.info is info
    assert list(source) == queued
    source.release()  # no-op, must not raise


# --- VideoFileSink over a fake sv.VideoSink ----------------------------------------


class FakeVideoSink:
    instances: list["FakeVideoSink"] = []

    def __init__(self, path, info):
        self.path = path
        self.info = info
        self.written: list[np.ndarray] = []
        self.entered = False
        self.exited = False
        FakeVideoSink.instances.append(self)

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, *exc):
        self.exited = True
        return False

    def write_frame(self, frame):
        self.written.append(frame)


def test_video_file_sink_writes_and_returns_true(monkeypatch, tmp_path):
    FakeVideoSink.instances.clear()
    monkeypatch.setattr("object_tracker.sinks.sv.VideoSink", FakeVideoSink)

    sink = VideoFileSink(tmp_path / "sub" / "out.mp4", _info(3))
    frame = np.zeros((48, 64, 3), dtype=np.uint8)

    assert sink.show(frame) is True
    sink.close()

    fake = FakeVideoSink.instances[-1]
    assert fake.entered is True
    assert fake.exited is True
    assert len(fake.written) == 1
