"""Week 11 acceptance: the pure P/PID step. No hardware, no network, no clock."""

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
    """Without this the turret hunts noise forever, jittering around centre at rest."""
    command, new_state = step((3.0, -2.0), _p_gains(), FRAME_ZERO, dt=0.1)
    assert command.pan_delta == pytest.approx(0.0)
    assert command.tilt_delta == pytest.approx(0.0)


def test_pan_follows_positive_x_error_directly():
    command, _ = step((20.0, 0.0), _p_gains(), FRAME_ZERO, dt=0.1)
    assert command.pan_delta == pytest.approx(2.0)  # kp * error = 0.1 * 20


def test_tilt_inverts_the_sign_of_y_error():
    """THE classic first bug on this project.

    +y means the target is BELOW centre (image coordinates). The camera must look further
    DOWN, and tilt_delta is +up — so the command must be negative. Get this backwards and
    every correction enlarges the error: the turret runs to its limit in about a second.
    """
    command, _ = step((0.0, 20.0), _p_gains(), FRAME_ZERO, dt=0.1)
    assert command.tilt_delta == pytest.approx(-2.0)


def test_output_clamps_at_positive_max_delta():
    """A pipeline stall means a huge error. The clamp is what stops a violent snap."""
    command, _ = step((1000.0, 0.0), _p_gains(), FRAME_ZERO, dt=0.1)
    assert command.pan_delta == pytest.approx(10.0)
