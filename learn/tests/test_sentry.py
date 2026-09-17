"""Week 12 acceptance: the dead-reckoned sweep state machine. Pure — numbers only."""

from __future__ import annotations

import pytest

from object_tracker.config import SentryConfig
from object_tracker.turret_sink.sentry import SentryState, observe_aim, step


@pytest.fixture
def config():
    """Built in a fixture, not at module scope, so an unimplemented SentryConfig fails this
    test rather than aborting collection for the whole suite."""
    return SentryConfig(
        grace_s=2.0, speed_deg_s=15.0,
        pan_min_deg=0.0, pan_max_deg=180.0,
        tilt_min_deg=20.0, tilt_max_deg=115.0,
        tilt_default_deg=90.0, max_delta_deg=5.0,
    )


def test_no_sweep_until_the_grace_period_elapses(config):
    """Don't thrash between track and sweep when a detection flickers."""
    state = SentryState()
    pan, tilt, state = step(state, dt=1.0, config=config)
    assert (pan, tilt) == (0.0, 0.0)
    assert state.unlocked_for_s == pytest.approx(1.0)

    pan, tilt, state = step(state, dt=0.5, config=config)
    assert (pan, tilt) == (0.0, 0.0), "still inside the 2s grace period"


def test_pan_sweeps_left_first_and_flips_at_the_bound(config):
    state = SentryState(pan_estimate_deg=90.0, unlocked_for_s=2.0)
    pan, _, state = step(state, dt=0.1, config=config)
    assert pan < 0, "the first sweep direction is left"

    # Drive all the way into the lower bound.
    for _ in range(300):
        _, _, state = step(state, dt=0.1, config=config)
        if state.direction > 0:
            break
    assert state.pan_estimate_deg == pytest.approx(config.pan_min_deg)
    assert state.direction > 0, "hitting the bound flips the sweep — and re-zeroes the drift"


def test_tilt_relocates_monotonically_to_default_without_overshoot(config):
    state = SentryState(tilt_estimate_deg=67.5, unlocked_for_s=2.0)
    previous = state.tilt_estimate_deg
    for _ in range(100):
        _, _, state = step(state, dt=0.1, config=config)
        assert state.tilt_estimate_deg >= previous, "monotone toward the patrol angle"
        assert state.tilt_estimate_deg <= config.tilt_default_deg, "never overshoots"
        previous = state.tilt_estimate_deg
    assert state.tilt_estimate_deg == pytest.approx(config.tilt_default_deg)


def test_a_stall_is_capped_at_max_delta(config):
    """A huge dt (a pipeline stall) must not produce a violent sweep jump."""
    state = SentryState(unlocked_for_s=2.0)
    pan, _, _ = step(state, dt=10.0, config=config)
    assert abs(pan) <= config.max_delta_deg


def test_observe_aim_resets_the_grace_timer_and_rearms_left(config):
    state = SentryState(pan_estimate_deg=90.0, unlocked_for_s=5.0, direction=+1.0)
    state = observe_aim(state, pan_delta=3.0, tilt_delta=-2.0, config=config)
    assert state.unlocked_for_s == 0.0
    assert state.direction == -1.0
    assert state.pan_estimate_deg == pytest.approx(93.0), "tracking nudges move the estimate too"
