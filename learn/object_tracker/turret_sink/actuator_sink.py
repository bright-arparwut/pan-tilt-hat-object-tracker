"""Actuator Sink (ADR-0013): the FrameSink that aims the turret instead of drawing.

**Glue only.** It pulls the frame's Track centres, threads Target Selector + Aim Controller,
and ships the resulting Aim Command down the configured transport. Every decision lives in a
pure function elsewhere; this class holds the mutable state and nothing else — the same
pure-step-wrapped-in-a-stateful-manager pattern as ``zoom.ZoomSlots``.

Look at how short it is when you're done. If yours is much longer, a decision has leaked in
here that belongs in ``aim_controller`` or ``sentry``.

Sentry mode (ADR-0014, week 12): unlocked frames thread the sentry state machine, and after
the grace period the sink ships sweep nudges down the same transport and the same ``seq``
sequence. The Pi cannot tell a sweep nudge from an aim nudge — by design.
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
    """A ``FrameSink`` that never draws; always returns ``True`` (never asks the loop to stop).

    ``clock`` is injected so the timing logic is testable without sleeping. Default
    ``time.monotonic`` — not ``time.time``, which can jump backwards when the system clock
    is adjusted, producing a negative ``dt`` inside a control loop.
    """

    def __init__(
        self,
        transport: AimTransport,
        gains: AimGains,
        frame_wh: tuple[int, int],
        sentry_config: SentryConfig | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        raise NotImplementedError("Week 11 — see learn/curriculum/week-11-visual-servoing.md")

    def show(self, frame: np.ndarray, tracks: sv.Detections | None = None) -> bool:
        """One frame: select the target, compute the nudge, ship it. Never stops the loop.

        Week 11 (locked path): pull ``_present_centers``, ``select_target``, compute
        ``error = target - frame_centre``, ``step`` it into an ``AimCommand``, send.

        Week 12 (unlocked path): thread ``sentry_step`` instead, and send only when it emits a
        nonzero nudge. On the locked path, also call ``observe_aim`` so the dead-reckoned pose
        keeps up with the tracking nudges.

        ``dt`` comes from the injected clock, floored at 0.0 — never trust a clock to be
        monotonic just because you asked for a monotonic one.
        """
        raise NotImplementedError("Week 11 — see learn/curriculum/week-11-visual-servoing.md")

    def close(self) -> None:
        raise NotImplementedError("Week 11 — see learn/curriculum/week-11-visual-servoing.md")
