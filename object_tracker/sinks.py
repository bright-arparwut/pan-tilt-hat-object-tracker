"""The Frame Sink seam (ADR-0010): where the loop's annotated frames go.

``pipeline.run`` calls ``sink.show(frame)`` for each annotated frame and stops when it
returns ``False`` — so termination is unified: the loop ends when the source is exhausted
**or** the sink says stop. ``VideoFileSink`` (always true) is the Offline path; ``WindowSink``
is the Live Preview and ``CompositeSink`` fans out to both for ``--record``.
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
    ``True`` to continue. ``close`` frees any underlying writer/window.
    """

    def show(self, frame: np.ndarray) -> bool: ...

    def close(self) -> None: ...


class VideoFileSink:
    """A ``FrameSink`` that writes annotated frames to an ``.mp4`` via ``sv.VideoSink``.

    Always returns ``True`` from ``show`` — a file sink never asks to stop, so the loop runs
    to source exhaustion (the Offline contract).
    """

    def __init__(self, path: Path, info: sv.VideoInfo) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._sink = sv.VideoSink(str(path), info)
        self._sink.__enter__()  # open the cv2.VideoWriter eagerly

    def show(self, frame: np.ndarray) -> bool:
        self._sink.write_frame(frame)
        return True

    def close(self) -> None:
        self._sink.__exit__(None, None, None)


class WindowSink:
    """A ``FrameSink`` that shows annotated frames in an on-screen window (Live Preview).

    ``show`` returns ``False`` when the user presses ``q`` **or** closes the window, so the
    loop's unified termination covers the viewer quitting as well as source exhaustion.
    """

    def __init__(self, window_name: str = DEFAULT_WINDOW_NAME) -> None:
        self._window_name = window_name

    def show(self, frame: np.ndarray) -> bool:
        cv2.imshow(self._window_name, frame)
        if (cv2.waitKey(1) & 0xFF) == ord("q"):
            return False
        # The user clicked the window's close button — the window is no longer visible.
        if cv2.getWindowProperty(self._window_name, cv2.WND_PROP_VISIBLE) < 1:
            return False
        return True

    def close(self) -> None:
        cv2.destroyWindow(self._window_name)


class CompositeSink:
    """A ``FrameSink`` that fans one frame out to several sinks (``--record`` = window+file).

    ``show`` calls **every** child (no short-circuit, so a file sink still records the frame
    even when the window asks to stop) and returns the logical AND of their results. ``close``
    closes every child even if one raises, then re-raises the first failure (never silently
    swallowed) — the loop's ``finally`` still releases the source regardless.
    """

    def __init__(self, sinks: list[FrameSink]) -> None:
        self._sinks = list(sinks)

    def show(self, frame: np.ndarray) -> bool:
        keep_going = True
        for sink in self._sinks:
            if not sink.show(frame):
                keep_going = False
        return keep_going

    def close(self) -> None:
        first_error: Exception | None = None
        for sink in self._sinks:
            try:
                sink.close()
            except Exception as exc:  # noqa: BLE001 - close the rest, surface one failure
                first_error = first_error or exc
        if first_error is not None:
            raise first_error
