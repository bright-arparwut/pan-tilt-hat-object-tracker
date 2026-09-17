"""The Frame Source seam (ADR-0010): where the loop's frames come from.

``pipeline.run`` iterates a ``FrameSource`` and sizes its annotators / progress bar from
``source.info`` — never branching on whether the frames came from a file or a camera.
``FileSource`` wraps the ``supervision`` file path; ``CameraSource`` wraps
``cv2.VideoCapture`` (a camera index or stream URL). This mirrors the ``Detector`` seam
(ADR-0009).

Week 1 builds ``FileSource`` only. Week 8 adds the Live half — and that is when you find out
whether the Protocol you wrote in week 1 was the right shape.
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
    """A ``FrameSource`` over a video file (the Offline path).

    Reads its ``VideoInfo`` from the file header at construction — resolution, fps and a
    known ``total_frames`` — so the loop can size annotators and the progress bar before the
    first frame is decoded.
    """

    def __init__(self, path: Path) -> None:
        raise NotImplementedError("Week 1 — see learn/curriculum/week-01-frame-io.md")

    def __iter__(self) -> Iterator[np.ndarray]:
        raise NotImplementedError("Week 1 — see learn/curriculum/week-01-frame-io.md")

    def release(self) -> None:
        """A file generator owns no long-lived handle to free. What should this do?"""
        raise NotImplementedError("Week 1 — see learn/curriculum/week-01-frame-io.md")


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

    Keep this pure — no filesystem check, no device probe. That is what makes the mode
    inference testable without a camera plugged in.
    """
    raise NotImplementedError("Week 8 — see learn/curriculum/week-08-live-mode.md")


class CameraSource:
    """A ``FrameSource`` over ``cv2.VideoCapture`` — a live camera index or stream URL.

    Unbounded (``total_frames=None``); ``VideoInfo`` is **derived** from the capture rather
    than read from a file header, with an fps fallback for devices that report 0. Frames are
    read sequentially in the loop (no background reader) — a slow loop sees driver-dropped
    frames or growing lag (ADR-0010 §Throughput).

    Raise a clear ``RuntimeError`` naming the target if the device won't open; a raw cv2
    failure here is unhelpfully silent.
    """

    def __init__(self, spec: CameraSpec) -> None:
        raise NotImplementedError("Week 8 — see learn/curriculum/week-08-live-mode.md")

    def _derive_info(self) -> sv.VideoInfo:
        """Build ``VideoInfo`` from the open capture's properties.

        Some devices report ``CAP_PROP_FPS == 0``. A positive nominal fps is still needed
        because it feeds annotator scaling, so fall back to ``DEFAULT_CAMERA_FPS``.
        """
        raise NotImplementedError("Week 8 — see learn/curriculum/week-08-live-mode.md")

    def __iter__(self) -> Iterator[np.ndarray]:
        raise NotImplementedError("Week 8 — see learn/curriculum/week-08-live-mode.md")

    def release(self) -> None:
        raise NotImplementedError("Week 8 — see learn/curriculum/week-08-live-mode.md")
