"""Sentry state machine (2026-07-22 design): no-target pan sweep with dead-reckoned pose.

Pure functions mirroring aim_controller.py's shape: a frozen-dataclass state threaded
through ``step``. The host has no pose feedback — the wire is relative deltas only — so
the state carries pan/tilt *estimates* that accumulate every shipped delta, clamped with
the same limits the Pi applies (turret/turret_pi/servo.py — deliberately no shared module).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..config import SentryConfig


@dataclass(frozen=True)
class SentryState:
    """Dead-reckoned pose + sweep bookkeeping. Estimates start at the Pi's startup
    recenter pose (servo.py CENTER: pan 90.0, tilt (20 + 115) / 2 = 67.5)."""

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

    Silent (zero deltas) until the grace period is exceeded; then emits a constant-speed
    sweep nudge (per-step magnitude capped at ``max_delta_deg`` — stall protection) and a
    tilt-relocation nudge toward ``tilt_default_deg`` that never overshoots. Estimates
    advance by exactly what is emitted; pan flips direction at the clamp bounds.
    """
    unlocked_for_s = state.unlocked_for_s + dt
    if dt <= 0.0 or unlocked_for_s <= config.grace_s:
        return 0.0, 0.0, replace(state, unlocked_for_s=unlocked_for_s)

    step_mag = min(config.speed_deg_s * dt, config.max_delta_deg)

    new_pan = _clamp(
        state.pan_estimate_deg + state.direction * step_mag,
        config.pan_min_deg,
        config.pan_max_deg,
    )
    pan_delta = new_pan - state.pan_estimate_deg
    hit_bound = new_pan in (config.pan_min_deg, config.pan_max_deg)
    direction = -state.direction if hit_bound else state.direction

    remaining = config.tilt_default_deg - state.tilt_estimate_deg
    tilt_delta = _clamp(remaining, -step_mag, step_mag)

    return pan_delta, tilt_delta, SentryState(
        pan_estimate_deg=new_pan,
        tilt_estimate_deg=state.tilt_estimate_deg + tilt_delta,
        direction=direction,
        unlocked_for_s=unlocked_for_s,
    )
