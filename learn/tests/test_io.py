"""Week 1 acceptance: frame I/O and loop teardown.

These are the contract. The edge cases are yours to add — see the week doc.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import supervision as sv

from object_tracker.pipeline import run
from object_tracker.sinks import VideoFileSink
from object_tracker.sources import FileSource


def _write_clip(path: Path, frames: int = 5, wh: tuple[int, int] = (64, 48)) -> Path:
    """A tiny real .mp4 so the tests exercise actual decoding, not a mock."""
    info = sv.VideoInfo(width=wh[0], height=wh[1], fps=10, total_frames=frames)
    with sv.VideoSink(str(path), info) as sink:
        for i in range(frames):
            frame = np.full((wh[1], wh[0], 3), i * 10, dtype=np.uint8)
            sink.write_frame(frame)
    return path


def test_file_source_reports_video_info(tmp_path):
    clip = _write_clip(tmp_path / "clip.mp4", frames=5, wh=(64, 48))
    source = FileSource(clip)
    assert source.info.resolution_wh == (64, 48)
    assert source.info.fps == 10
    assert source.info.total_frames == 5


def test_video_file_sink_writes_every_frame(tmp_path):
    clip = _write_clip(tmp_path / "clip.mp4", frames=5)
    source = FileSource(clip)
    out = tmp_path / "nested" / "out.mp4"      # parent does not exist — sink must create it
    sink = VideoFileSink(out, source.info)
    for frame in source:
        assert sink.show(frame) is True         # a file sink never asks the loop to stop
    sink.close()
    assert out.exists()
    assert sv.VideoInfo.from_video_path(str(out)).total_frames == 5


class _PassthroughDetector:
    """Stands in for week 2's detector so week 1 can exercise the loop on its own."""

    def detect(self, frame):
        return sv.Detections.empty()


def test_pipeline_releases_source_even_when_sink_close_raises(tmp_path):
    """The contract that matters: a failing teardown must not strand another resource."""
    clip = _write_clip(tmp_path / "clip.mp4", frames=3)
    source = FileSource(clip)
    released = []
    source.release = lambda: released.append(True)  # type: ignore[method-assign]

    class ExplodingSink:
        def show(self, frame, tracks=None):
            return True

        def close(self):
            raise RuntimeError("window close failed")

    # Stand-ins for the configs: both features off, which is all week 1's loop needs to know.
    off = SimpleNamespace(enabled=False)

    with pytest.raises(RuntimeError, match="window close failed"):
        run(_PassthroughDetector(), source, ExplodingSink(), off, off)

    assert released == [True], "the source must be released even though sink.close() raised"
