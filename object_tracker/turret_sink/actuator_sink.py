"""Actuator Sink (ADR-0013): the FrameSink that aims the turret instead of drawing.

Glue only — pulls the frame's Track centres, threads Target Selector + Aim Controller, and
ships the resulting Aim Command down the configured AimTransport. Mirrors the existing
sinks.py shape: a thin, stateful wrapper around pure functions, the same
pure-step-wrapped-in-a-stateful-manager pattern zoom.py's ZoomSlots already uses.
"""

from __future__ import annotations

import time

import numpy as np
import supervision as sv

from ..config import AimGains
from ..tracking import _present_centers
from .aim_controller import AimControllerState, step
from .target_selector import select_target
from .transport import AimTransport


class ActuatorSink:
    """A FrameSink that never draws; always returns True (never asks the loop to stop)."""

    def __init__(
        self, transport: AimTransport, gains: AimGains, frame_wh: tuple[int, int]
    ) -> None:
        self._transport = transport
        self._gains = gains
        self._center = (frame_wh[0] / 2.0, frame_wh[1] / 2.0)
        self._locked_id: int | None = None
        self._state = AimControllerState()
        self._last_ts: float | None = None

    def show(self, frame: np.ndarray, tracks: sv.Detections | None = None) -> bool:
        present = _present_centers(tracks) if tracks is not None else {}
        self._locked_id = select_target(frozenset(present.keys()), self._locked_id)
        now = time.monotonic()
        dt = 0.0 if self._last_ts is None else max(0.0, now - self._last_ts)
        self._last_ts = now
        if self._locked_id is not None:
            target = present[self._locked_id]
            error = (target[0] - self._center[0], target[1] - self._center[1])
            command, self._state = step(error, self._gains, self._state, dt)
            self._transport.send(command)
        return True

    def close(self) -> None:
        self._transport.close()
