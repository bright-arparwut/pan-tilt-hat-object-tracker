"""The Frame Sink seam (ADR-0010): where the loop's annotated frames go.

``pipeline.run`` calls ``sink.show(frame)`` for each annotated frame and stops when it
returns ``False`` — so termination is unified: the loop ends when the source is exhausted
**or** the sink says stop. ``VideoFileSink`` (always true) is the Offline path; ``WindowSink``
is the Live Preview and ``CompositeSink`` fans out to both for ``--record``.

Week 1 builds ``VideoFileSink``. Week 8 adds the other two. Week 11's ``ActuatorSink`` is a
``FrameSink`` too — it satisfies this Protocol and aims a motor instead of drawing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import cv2
import numpy as np
import supervision as sv

DEFAULT_WINDOW_NAME = "object-tracker — q to quit"


class FrameSink(Protocol):
    """A destination for annotated frames.

    ``show`` returns ``False`` to ask the loop to stop (e.g. the viewer pressed ``q``);
    ``True`` to continue. ``tracks`` carries the frame's confirmed Tracks under ``--track``
    (``None`` otherwise) — sinks that don't need it ignore it; the Actuator Sink is why it
    exists. ``close`` frees any underlying writer/window.
    """

    def show(self, frame: np.ndarray, tracks: sv.Detections | None = None) -> bool: ...

    def close(self) -> None: ...


class VideoFileSink:
    """A ``FrameSink`` that writes annotated frames to an ``.mp4`` via ``sv.VideoSink``.

    Always returns ``True`` from ``show`` — a file sink never asks to stop, so the loop runs
    to source exhaustion (the Offline contract). Create the parent directory if it is
    missing, and open the underlying writer **eagerly** in ``__init__`` so a bad path fails
    before the run starts rather than on frame 1.
    """

    def __init__(self, path: Path, info: sv.VideoInfo) -> None:
        raise NotImplementedError("Week 1 — see learn/curriculum/week-01-frame-io.md")

    def show(self, frame: np.ndarray, tracks: sv.Detections | None = None) -> bool:
        raise NotImplementedError("Week 1 — see learn/curriculum/week-01-frame-io.md")

    def close(self) -> None:
        raise NotImplementedError("Week 1 — see learn/curriculum/week-01-frame-io.md")


class WindowSink:
    """A ``FrameSink`` that shows annotated frames in an on-screen window (Live Preview).

    ``show`` returns ``False`` when the user presses ``q`` **or** closes the window, so the
    loop's unified termination covers the viewer quitting as well as source exhaustion.

    Both quit paths matter. The close-button one is the one people forget: after the window
    is gone, ``cv2.waitKey`` alone will happily report "no key pressed" forever.
    """

    def __init__(self, window_name: str = DEFAULT_WINDOW_NAME) -> None:
        raise NotImplementedError("Week 8 — see learn/curriculum/week-08-live-mode.md")

    def show(self, frame: np.ndarray, tracks: sv.Detections | None = None) -> bool:
        raise NotImplementedError("Week 8 — see learn/curriculum/week-08-live-mode.md")

    def close(self) -> None:
        raise NotImplementedError("Week 8 — see learn/curriculum/week-08-live-mode.md")


class CompositeSink:
    """A ``FrameSink`` that fans one frame out to several sinks (``--record`` = window+file,
    or ``--record`` + ``--turret`` = window+file+actuator).

    ``show`` calls **every** child — no short-circuit, so a file sink still records the frame
    even when the window asks to stop — and returns the logical AND of their results,
    forwarding ``tracks`` to each unchanged.

    ``close`` closes every child even if one raises, then re-raises the first failure (never
    silently swallowed). Work out why "close them all, then raise" beats "raise on the first
    failure": what leaks in the second version?
    """

    def __init__(self, sinks: list[FrameSink]) -> None:
        raise NotImplementedError("Week 8 — see learn/curriculum/week-08-live-mode.md")

    def show(self, frame: np.ndarray, tracks: sv.Detections | None = None) -> bool:
        raise NotImplementedError("Week 8 — see learn/curriculum/week-08-live-mode.md")

    def close(self) -> None:
        raise NotImplementedError("Week 8 — see learn/curriculum/week-08-live-mode.md")
