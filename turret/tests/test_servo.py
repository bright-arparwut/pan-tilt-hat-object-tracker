from __future__ import annotations

from turret_pi.servo import ServoAngles, clamp_angles


def test_clamp_within_range_is_unchanged():
    assert clamp_angles(ServoAngles(90.0, 45.0)) == ServoAngles(90.0, 45.0)


def test_clamp_pan_above_max():
    assert clamp_angles(ServoAngles(200.0, 45.0)) == ServoAngles(180.0, 45.0)


def test_clamp_pan_below_min():
    assert clamp_angles(ServoAngles(-10.0, 45.0)) == ServoAngles(0.0, 45.0)


def test_clamp_tilt_above_max():
    assert clamp_angles(ServoAngles(90.0, 250.0)) == ServoAngles(90.0, 180.0)


def test_clamp_tilt_below_min():
    assert clamp_angles(ServoAngles(90.0, -50.0)) == ServoAngles(90.0, 0.0)
