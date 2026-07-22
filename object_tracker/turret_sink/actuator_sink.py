"""Actuator Sink (ADR-0013): the FrameSink that aims the turret instead of drawing.

Glue only — pulls the frame's Track centres, threads Target Selector + Aim Controller, and
ships the resulting Aim Command down the configured AimTransport. Mirrors the existing
sinks.py shape: a thin, stateful wrapper around pure functions, the same
pure-step-wrapped-in-a-stateful-manager pattern zoom.py's ZoomSlots already uses.

Sentry mode (2026-07-22 design): unlocked frames thread the sentry state machine; after
the grace period the sink ships sweep nudges through the same transport/seq path. All
decisions live in sentry.py — this class stays glue.
"""

from __future__ import annotations

import time
from typing import Callable

import numpy as np
import supervision as sv

from ..config import AimGains, SentryConfig
from ..tracking import _present_centers
from .aim_controller import AimCommand, AimControllerState, step
from .sentry import SentryState, observe_aim
from .sentry import step as sentry_step
from .target_selector import select_target
from .transport import AimTransport


class ActuatorSink:
    """A FrameSink that never draws; always returns True (never asks the loop to stop)."""

    def __init__(
        self,
        transport: AimTransport,
        gains: AimGains,
        frame_wh: tuple[int, int],
        sentry_config: SentryConfig | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transport = transport
        self._gains = gains
        self._center = (frame_wh[0] / 2.0, frame_wh[1] / 2.0)
        self._locked_id: int | None = None
        self._state = AimControllerState()
        self._last_ts: float | None = None
        self._sentry_config = (
            sentry_config if sentry_config is not None else SentryConfig()
        )
        self._sentry = SentryState()
        self._clock = clock

    def show(self, frame: np.ndarray, tracks: sv.Detections | None = None) -> bool:
        present = _present_centers(tracks) if tracks is not None else {}
        self._locked_id = select_target(frozenset(present.keys()), self._locked_id)
        now = self._clock()
        dt = 0.0 if self._last_ts is None else max(0.0, now - self._last_ts)
        self._last_ts = now
        if self._locked_id is not None:
            target = present[self._locked_id]
            error = (target[0] - self._center[0], target[1] - self._center[1])
            command, self._state = step(error, self._gains, self._state, dt)
            self._transport.send(command)
            self._sentry = observe_aim(
                self._sentry, command.pan_delta, command.tilt_delta, self._sentry_config
            )
        else:
            pan_delta, tilt_delta, self._sentry = sentry_step(
                self._sentry, dt, self._sentry_config
            )
            if pan_delta != 0.0 or tilt_delta != 0.0:
                self._transport.send(
                    AimCommand(pan_delta=pan_delta, tilt_delta=tilt_delta)
                )
        return True

    def close(self) -> None:
        self._transport.close()
