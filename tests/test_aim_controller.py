"""Unit tests for the Aim Controller (ADR-0013): pure P/PID step.

No hardware, no network — exercises ``step`` directly with synthetic pixel errors.
"""

from __future__ import annotations

import pytest

from object_tracker.config import AimGains
from object_tracker.turret_sink.aim_controller import AimControllerState, step

FRAME_ZERO = AimControllerState()


def _p_gains(**overrides):
    base = dict(kp=0.1, ki=0.0, kd=0.0, deadzone_px=5.0, max_delta_deg=10.0)
    base.update(overrides)
    return AimGains(**base)


def test_error_inside_deadzone_produces_zero_command():
    command, new_state = step((3.0, -2.0), _p_gains(), FRAME_ZERO, dt=0.1)
    assert command.pan_delta == pytest.approx(0.0)
    assert command.tilt_delta == pytest.approx(0.0)
    assert new_state == AimControllerState(0.0, 0.0, 0.0, 0.0)


def test_pan_follows_positive_x_error_directly():
    command, _ = step((20.0, 0.0), _p_gains(), FRAME_ZERO, dt=0.1)
    assert command.pan_delta == pytest.approx(2.0)  # kp * error = 0.1 * 20


def test_tilt_inverts_the_sign_of_y_error():
    # +y (target below centre, image coords) must drive tilt_delta *negative* (+up convention).
    command, _ = step((0.0, 20.0), _p_gains(), FRAME_ZERO, dt=0.1)
    assert command.tilt_delta == pytest.approx(-2.0)


def test_output_clamps_at_positive_max_delta():
    command, _ = step((1000.0, 0.0), _p_gains(), FRAME_ZERO, dt=0.1)
    assert command.pan_delta == pytest.approx(10.0)


def test_output_clamps_at_negative_max_delta():
    command, _ = step((-1000.0, 0.0), _p_gains(), FRAME_ZERO, dt=0.1)
    assert command.pan_delta == pytest.approx(-10.0)


def test_integral_term_accumulates_across_steps():
    gains = _p_gains(kp=0.0, ki=1.0, deadzone_px=0.0, max_delta_deg=100.0)
    command1, state1 = step((10.0, 0.0), gains, AimControllerState(), dt=1.0)
    assert command1.pan_delta == pytest.approx(10.0)  # ki * (0 + 10*1)
    command2, state2 = step((10.0, 0.0), gains, state1, dt=1.0)
    assert state2.integral_x == pytest.approx(20.0)
    assert command2.pan_delta == pytest.approx(20.0)  # ki * (10 + 10*1)


def test_derivative_term_reacts_only_to_the_change_in_error():
    gains = _p_gains(kp=0.0, ki=0.0, kd=1.0, deadzone_px=0.0, max_delta_deg=100.0)
    command1, state1 = step((10.0, 0.0), gains, AimControllerState(), dt=1.0)
    assert command1.pan_delta == pytest.approx(10.0)  # kd * (10 - 0) / 1
    command2, _ = step((10.0, 0.0), gains, state1, dt=1.0)
    assert command2.pan_delta == pytest.approx(0.0)  # kd * (10 - 10) / 1


def test_zero_dt_does_not_raise_and_yields_no_derivative_contribution():
    gains = _p_gains(kp=0.0, ki=0.0, kd=1.0, deadzone_px=0.0, max_delta_deg=100.0)
    command, _ = step((10.0, 0.0), gains, AimControllerState(), dt=0.0)
    assert command.pan_delta == pytest.approx(0.0)
