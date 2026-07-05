from __future__ import annotations

from turret_pi.servo import (
    CENTER,
    SERVO_ACTUATION_RANGE_DEG,
    SERVO_MAX_US,
    SERVO_MIN_US,
    ServoAngles,
    ServoDriver,
    clamp_angles,
)


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


class _FakeChannel:
    """One PCA9685 channel: records the last angle written and the calibration applied."""

    def __init__(self) -> None:
        self.angle: float | None = None
        self.actuation_range: float | None = None
        self.pulse_range: tuple[int, int] | None = None

    def set_pulse_width_range(self, min_us: int, max_us: int) -> None:
        self.pulse_range = (min_us, max_us)


class FakeKit:
    """Stand-in for adafruit ServoKit: `servo[ch]` yields a recordable channel (no HAT)."""

    def __init__(self) -> None:
        self.servo = {0: _FakeChannel(), 1: _FakeChannel()}


def test_startup_centers_both_channels():
    kit = FakeKit()
    driver = ServoDriver(kit=kit)
    assert kit.servo[0].angle == 90.0
    assert kit.servo[1].angle == 90.0
    assert driver.current == CENTER


def test_configures_pulse_range_and_actuation_on_both_channels():
    kit = FakeKit()
    ServoDriver(kit=kit)
    for channel in (0, 1):
        assert kit.servo[channel].actuation_range == SERVO_ACTUATION_RANGE_DEG
        assert kit.servo[channel].pulse_range == (SERVO_MIN_US, SERVO_MAX_US)


def test_apply_delta_accumulates_onto_pose_and_writes_both_channels():
    kit = FakeKit()
    driver = ServoDriver(kit=kit)
    driver.apply_delta(5.0, -5.0)
    assert driver.current == ServoAngles(95.0, 85.0)
    assert kit.servo[0].angle == 95.0
    assert kit.servo[1].angle == 85.0


def test_successive_deltas_accumulate_relative_not_absolute():
    driver = ServoDriver(kit=FakeKit())
    driver.apply_delta(5.0, 0.0)
    driver.apply_delta(5.0, 0.0)
    assert driver.current == ServoAngles(100.0, 90.0)


def test_delta_past_a_limit_is_clamped_and_never_writes_out_of_range():
    kit = FakeKit()
    driver = ServoDriver(kit=kit)
    driver.apply_delta(200.0, 0.0)  # 90 + 200 = 290 -> clamped to 180
    assert driver.current == ServoAngles(180.0, 90.0)
    assert kit.servo[0].angle == 180.0  # the raw 290 is never written


def test_axis_signs_reverse_the_written_direction(monkeypatch):
    monkeypatch.setattr("turret_pi.servo.PAN_SIGN", -1.0)
    driver = ServoDriver(kit=FakeKit())
    driver.apply_delta(5.0, 0.0)  # with PAN_SIGN=-1: 90 + (-1)*5 = 85
    assert driver.current.pan_deg == 85.0


def test_recenter_returns_to_center_after_a_move():
    kit = FakeKit()
    driver = ServoDriver(kit=kit)
    driver.apply_delta(5.0, -5.0)
    driver.recenter()
    assert driver.current == CENTER
    assert kit.servo[0].angle == 90.0
    assert kit.servo[1].angle == 90.0
