"""Servo control (ADR-0013 roadmap Phase 1): both halves of the servo layer.

The pure, hardware-free half — ``ServoAngles`` plus mechanical-limit ``clamp_angles`` — comes
first, followed by the real I²C ``ServoDriver`` (HAT/PCA9685 I/O over an injectable adafruit
ServoKit). Everything above the driver stays hardware-free and unit-testable on the Mac; only
``ServoDriver`` touches the SDK, behind a lazy import reached solely when no kit is injected.
"""

from __future__ import annotations

from dataclasses import dataclass

# Mechanical limits (deg) for the Waveshare Pan-Tilt HAT's servos — clamped in software so a
# stray command never stalls or strips a servo (roadmap Phase 1 gotcha).
PAN_MIN_DEG = 0.0
PAN_MAX_DEG = 180.0
TILT_MIN_DEG = 0.0
TILT_MAX_DEG = 180.0


@dataclass(frozen=True)
class ServoAngles:
    """An absolute pan/tilt pose in degrees."""

    pan_deg: float
    tilt_deg: float


def clamp_angles(angles: ServoAngles) -> ServoAngles:
    """Clamp both axes to the HAT's mechanical limits (pure, hardware-free)."""
    return ServoAngles(
        pan_deg=max(PAN_MIN_DEG, min(PAN_MAX_DEG, angles.pan_deg)),
        tilt_deg=max(TILT_MIN_DEG, min(TILT_MAX_DEG, angles.tilt_deg)),
    )


# --- Real I²C driver (ADR-0013 Phase 1) --------------------------------------------------
# The hardware-bound half: turns relative Aim Command nudges into absolute, clamped servo
# positions and writes them to the PCA9685. The only hardware-coupled unit in turret_pi.

PAN_CHANNEL = 0
TILT_CHANNEL = 1
CENTER = ServoAngles(pan_deg=90.0, tilt_deg=90.0)  # mid-range on both axes

# Per-servo calibration — measured with the Phase-1 teleop harness, then frozen (spec D3).
SERVO_MIN_US = 500
SERVO_MAX_US = 2500
SERVO_ACTUATION_RANGE_DEG = 180.0
PAN_SIGN = +1.0   # +pan_delta (target right) -> which way pan_deg moves; flip if reversed
TILT_SIGN = +1.0  # +tilt_delta (target up)   -> which way tilt_deg moves; flip if reversed


class ServoDriver:
    """Real I²C driver for the Waveshare Pan-Tilt HAT (PCA9685). Implements the ``Servo``
    Protocol the listener depends on. ``kit`` is injectable so the driver is unit-testable
    with a fake kit on the Mac; ``kit=None`` constructs the real ServoKit (lazy import)."""

    def __init__(self, kit=None, center: ServoAngles = CENTER) -> None:
        if kit is None:
            # Lazy/Pi-only: keeps every turret_pi module importable on the Mac for tests
            # without adafruit-blinka installed (spec §Testing, Global Constraints).
            from adafruit_servokit import ServoKit

            kit = ServoKit(channels=16)
        self._kit = kit
        self._center = center
        for channel in (PAN_CHANNEL, TILT_CHANNEL):
            servo = kit.servo[channel]
            servo.actuation_range = SERVO_ACTUATION_RANGE_DEG
            servo.set_pulse_width_range(SERVO_MIN_US, SERVO_MAX_US)
        self._write(center)  # sets self._current and moves the HAT to center on startup

    def _write(self, angles: ServoAngles) -> None:
        """Write an absolute pose to both channels and record it (single write path)."""
        self._kit.servo[PAN_CHANNEL].angle = angles.pan_deg
        self._kit.servo[TILT_CHANNEL].angle = angles.tilt_deg
        self._current = angles  # replaced, never mutated (repo immutability style)

    def apply_delta(self, pan_delta: float, tilt_delta: float) -> None:
        """Accumulate a relative nudge onto the current pose, clamp to mechanical limits,
        write both channels. Never raises on a large delta — clamp makes it safe."""
        target = ServoAngles(
            pan_deg=self._current.pan_deg + PAN_SIGN * pan_delta,
            tilt_deg=self._current.tilt_deg + TILT_SIGN * tilt_delta,
        )
        self._write(clamp_angles(target))

    def recenter(self) -> None:
        """Return to the mechanical center (absolute write; sign-independent). Called on
        shutdown to leave the turret in a known safe pose."""
        self._write(self._center)

    @property
    def current(self) -> ServoAngles:
        """Where the turret is pointing now (post-clamp)."""
        return self._current
