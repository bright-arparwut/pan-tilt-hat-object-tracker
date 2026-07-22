"""Unit tests for the sentry state machine (sentry design 2026-07-22).

Pure functions — no hardware, no sockets; time is faked via explicit ``dt``.
One test per spec invariant, AAA style.
"""

from __future__ import annotations

from object_tracker.config import SentryConfig
from object_tracker.turret_sink.sentry import SentryState, step

CFG = SentryConfig()  # grace 2.0 s, 15 deg/s, pan 0-180, tilt 20-115, default 90, max_delta 5


def test_no_output_while_below_grace_period():
    state = SentryState()

    pan, tilt, state = step(state, dt=1.0, config=CFG)  # unlocked_for 1.0 <= 2.0

    assert (pan, tilt) == (0.0, 0.0)
    assert state.unlocked_for_s == 1.0


def test_output_begins_on_the_frame_that_crosses_grace():
    state = SentryState()
    _, _, state = step(state, dt=1.0, config=CFG)  # 1.0 — silent
    _, _, state = step(state, dt=1.0, config=CFG)  # 2.0 — still not > grace, silent

    pan, tilt, state = step(state, dt=0.1, config=CFG)  # 2.1 > 2.0 — sweep starts

    assert pan != 0.0


def test_dt_zero_emits_no_motion():
    state = SentryState(unlocked_for_s=10.0)  # far past grace

    pan, tilt, new_state = step(state, dt=0.0, config=CFG)

    assert (pan, tilt) == (0.0, 0.0)
    assert new_state.pan_estimate_deg == state.pan_estimate_deg


def _past_grace(pan: float = 90.0, direction: float = -1.0) -> SentryState:
    """A state already past the grace period, so step() sweeps immediately."""
    return SentryState(
        pan_estimate_deg=pan,
        tilt_estimate_deg=CFG.tilt_default_deg,
        direction=direction,
        unlocked_for_s=CFG.grace_s + 1.0,
    )


def test_first_sweep_direction_is_left():
    pan, _, _ = step(_past_grace(), dt=0.1, config=CFG)

    assert pan < 0.0  # decreasing pan = left
    assert pan == -CFG.speed_deg_s * 0.1  # constant speed: 15 deg/s * 0.1 s


def test_direction_flips_at_the_low_bound_and_estimate_stays_in_range():
    state = _past_grace(pan=0.5, direction=-1.0)

    pan, _, state = step(state, dt=0.1, config=CFG)  # wants -1.5, only 0.5 available

    assert pan == -0.5  # truncated at the bound
    assert state.pan_estimate_deg == CFG.pan_min_deg
    assert state.direction == 1.0  # flipped

    pan, _, state = step(state, dt=0.1, config=CFG)  # now sweeps right
    assert pan > 0.0


def test_direction_flips_at_the_high_bound():
    state = _past_grace(pan=179.9, direction=1.0)

    pan, _, state = step(state, dt=0.1, config=CFG)

    assert state.pan_estimate_deg == CFG.pan_max_deg
    assert state.direction == -1.0


def test_large_dt_output_is_clamped_to_max_delta_on_both_axes():
    state = SentryState(  # tilt far from default so both axes want a big step
        pan_estimate_deg=90.0,
        tilt_estimate_deg=CFG.tilt_min_deg,
        direction=-1.0,
        unlocked_for_s=CFG.grace_s + 1.0,
    )

    pan, tilt, _ = step(state, dt=10.0, config=CFG)  # 15 deg/s * 10 s = 150, clamp 5

    assert abs(pan) == CFG.max_delta_deg
    assert abs(tilt) <= CFG.max_delta_deg
