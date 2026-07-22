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
