"""The Frame Source seam (ADR-0010): where the loop's frames come from.

``pipeline.run`` iterates a ``FrameSource`` and sizes its annotators / progress bar from
``source.info`` — never branching on whether the frames came from a file or a camera. ``FileSource`` wraps the ``supervision`` file path; ``CameraSource`` wraps
``cv2.VideoCapture`` (a camera index or stream URL). This mirrors the ``Detector`` seam
(ADR-0009).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol
from urllib.parse import urlparse

import cv2
import numpy as np
import supervision as sv

from .config import DEFAULT_CAMERA_FPS

# URL schemes cv2.VideoCapture can open directly — anything else is treated as a file path.
_STREAM_SCHEMES = frozenset({"rtsp", "http", "https", "udp", "tcp"})


class FrameSource(Protocol):
    """A source of frames plus the ``VideoInfo`` the loop needs to size itself.

    ``info.total_frames`` is an int for bounded (file) sources and ``None`` for unbounded
    (live) ones, which the loop passes straight to ``tqdm`` as the progress total.
    """

    info: sv.VideoInfo

    def __iter__(self) -> Iterator[np.ndarray]: ...

    def release(self) -> None: ...


class FileSource:
    """A ``FrameSource`` over a video file (today's Offline path, unchanged behaviour)."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self.info = sv.VideoInfo.from_video_path(str(path))

    def __iter__(self) -> Iterator[np.ndarray]:
        return iter(sv.get_video_frames_generator(str(self._path)))

    def release(self) -> None:
        # A file generator owns no long-lived handle to free; nothing to release.
        return None


@dataclass(frozen=True)
class CameraSpec:
    """A Live source: a camera ``int`` index or a stream URL ``str`` (ADR-0010)."""

    target: int | str


@dataclass(frozen=True)
class FileSpec:
    """An Offline source: a path to a video file."""

    path: Path


def classify_source(text: str) -> CameraSpec | FileSpec:
    """Infer the source kind from ``--source`` shape (pure, no IO; ADR-0010).

    All-digits → camera **index**; a ``{rtsp,http,https,udp,tcp}`` URL scheme → **stream**;
    anything else → **file path**. ``cv2.VideoCapture`` opens both Live shapes, so stream
    support comes free alongside the local webcam.
    """
    if text.isdigit():
        return CameraSpec(int(text))
    if urlparse(text).scheme.lower() in _STREAM_SCHEMES:
        return CameraSpec(text)
    return FileSpec(Path(text))


class CameraSource:
    """A ``FrameSource`` over ``cv2.VideoCapture`` — a live camera index or stream URL.

    Unbounded (``total_frames=None``); ``VideoInfo`` is **derived** from the capture rather
    than read from a file header, with an fps fallback for devices that report 0. Frames are
    read sequentially in the loop (no background reader) — a slow loop sees driver-dropped
    frames or growing lag (ADR-0010 §Throughput).
    """

    def __init__(self, spec: CameraSpec) -> None:
        self._cap = cv2.VideoCapture(spec.target)
        if not self._cap.isOpened():
            raise RuntimeError(f"could not open live source: {spec.target!r}")
        self.info = self._derive_info()

    def _derive_info(self) -> sv.VideoInfo:
        width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        reported = self._cap.get(cv2.CAP_PROP_FPS)
        fps = round(reported) if reported and reported > 0 else DEFAULT_CAMERA_FPS
        return sv.VideoInfo(width=width, height=height, fps=fps, total_frames=None)

    def __iter__(self) -> Iterator[np.ndarray]:
        while True:
            ok, frame = self._cap.read()
            if not ok:
                break
            yield frame

    def release(self) -> None:
        self._cap.release()
