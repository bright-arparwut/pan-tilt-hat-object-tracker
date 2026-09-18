"""Week 8 acceptance: mode inference from --source shape (pure, no devices touched)."""

from __future__ import annotations

from pathlib import Path

import pytest

from object_tracker.sources import CameraSpec, FileSpec, classify_source


@pytest.mark.parametrize(
    "text, expected",
    [
        ("0", CameraSpec(0)),
        ("2", CameraSpec(2)),
        ("rtsp://camera.local/stream", CameraSpec("rtsp://camera.local/stream")),
        ("http://pi.local:8000/stream.mjpg", CameraSpec("http://pi.local:8000/stream.mjpg")),
        ("clip.mp4", FileSpec(Path("clip.mp4"))),
        ("/abs/path/clip.mp4", FileSpec(Path("/abs/path/clip.mp4"))),
    ],
)
def test_classify_source_maps_digits_urls_and_paths(text, expected):
    assert classify_source(text) == expected
