"""Sentry state machine (ADR-0014): no-target pan sweep with a dead-reckoned pose.

Pure functions mirroring ``aim_controller``'s shape: a frozen dataclass threaded through
``step``. No I/O, no clock — ``dt`` is an argument.

**The interesting constraint:** the host has no pose feedback. The wire carries relative
deltas only and the Pi never reports where it is pointing. So the state carries pan/tilt
*estimates* that accumulate every delta the host ships, clamped with host-side **mirrors** of
the Pi's limits (``turret/turret_pi/servo.py`` — deliberately no shared module, ADR-0013).

Those estimates drift. Pan self-corrects: every half-sweep drives both the estimate and the
real servo into the same hard mechanical limit, re-zeroing the error for free. Tilt has no
such re-zeroing point, so its drift is bounded-but-accumulating — and the project **accepts**
it rather than adding a feedback channel. Be able to explain why that is the right call.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..config import SentryConfig


@dataclass(frozen=True)
class SentryState:
    """Dead-reckoned pose + sweep bookkeeping.

    Estimates start at the Pi's startup recenter pose — the mid-range of each axis's
    measured mechanical limits (``servo.py``'s ``CENTER``). If you re-measured your own
    limits in week 9, these defaults must match them.
    """

    pan_estimate_deg: float = 90.0
    tilt_estimate_deg: float = 67.5
    direction: float = -1.0  # -1 = sweeping left, +1 = right; first sweep is left
    unlocked_for_s: float = 0.0  # time since the last locked frame


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def step(
    state: SentryState, dt: float, config: SentryConfig
) -> tuple[float, float, SentryState]:
    """One unlocked frame. Returns ``(pan_delta, tilt_delta, new_state)``.

    Silent (zero deltas) until the grace period is exceeded — don't start sweeping the
    instant a track blinks out, or a flickering detection makes the turret thrash.

    After the grace period: a constant-speed pan sweep (per-step magnitude capped at
    ``max_delta_deg``, so a pipeline stall producing a huge ``dt`` cannot produce a violent
    jump), plus a tilt nudge toward ``tilt_default_deg`` that **never overshoots** — clamp
    the remaining distance, don't step blindly past it.

    The estimates advance by exactly what is emitted, never by what was intended. Pan flips
    ``direction`` when it reaches a clamp bound; that is the triangle wave, and it is also
    the moment the drift re-zeroes.
    """
    raise NotImplementedError("Week 12 — see learn/curriculum/week-12-sentry-integration.md")


def observe_aim(
    state: SentryState, pan_delta: float, tilt_delta: float, config: SentryConfig
) -> SentryState:
    """A locked frame shipped an Aim Command: fold its deltas into the estimates.

    Clamp exactly as the Pi clamps (so the estimate tracks what the hardware actually did,
    not what was asked), reset the grace timer, and re-arm the first sweep direction (left).

    This is what keeps the two modes coherent: tracking nudges and sweep nudges both move the
    turret, so both must move the estimate.
    """
    raise NotImplementedError("Week 12 — see learn/curriculum/week-12-sentry-integration.md")
