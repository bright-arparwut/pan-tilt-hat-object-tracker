"""Week 9 acceptance: the servo layer. All four run on your Mac with a fake kit."""

from __future__ import annotations

import pytest

from turret_pi.servo import (
    CENTER,
    PAN_MAX_DEG,
    PAN_MIN_DEG,
    TILT_MAX_DEG,
    TILT_MIN_DEG,
    ServoAngles,
    ServoDriver,
    clamp_angles,
)


class _FakeServo:
    def __init__(self):
        self.angle = None
        self.actuation_range = None
        self.pulse_range = None

    def set_pulse_width_range(self, lo, hi):
        self.pulse_range = (lo, hi)


class _FakeKit:
    """Stands in for adafruit ServoKit. This is why the driver takes an injectable kit."""

    def __init__(self):
        self.servo = {0: _FakeServo(), 1: _FakeServo()}


def test_clamp_holds_an_angle_inside_the_limits():
    angles = ServoAngles(pan_deg=90.0, tilt_deg=60.0)
    assert clamp_angles(angles) == angles


def test_clamp_pins_tilt_to_the_measured_bracket_limits():
    """Commanding past a mechanical stop stalls the motor. The clamp is the safety net."""
    assert clamp_angles(ServoAngles(0.0, -50.0)).tilt_deg == TILT_MIN_DEG
    assert clamp_angles(ServoAngles(0.0, 999.0)).tilt_deg == TILT_MAX_DEG
    assert clamp_angles(ServoAngles(-999.0, 60.0)).pan_deg == PAN_MIN_DEG
    assert clamp_angles(ServoAngles(999.0, 60.0)).pan_deg == PAN_MAX_DEG


def test_apply_delta_accumulates_onto_the_current_pose_and_clamps():
    kit = _FakeKit()
    driver = ServoDriver(kit=kit)
    assert driver.current == CENTER, "a fresh turret takes the safe pose before any command"

    driver.apply_delta(10.0, 5.0)
    assert driver.current.pan_deg == pytest.approx(CENTER.pan_deg + 10.0)
    assert kit.servo[0].angle == pytest.approx(CENTER.pan_deg + 10.0)

    driver.apply_delta(9999.0, 0.0)  # must clamp, never raise
    assert driver.current.pan_deg == pytest.approx(PAN_MAX_DEG)


def test_recenter_writes_the_safe_center_pose():
    kit = _FakeKit()
    driver = ServoDriver(kit=kit)
    driver.apply_delta(30.0, 20.0)
    driver.recenter()
    assert driver.current == CENTER
    assert kit.servo[1].angle == pytest.approx(CENTER.tilt_deg)
