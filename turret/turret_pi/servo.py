"""Servo angles (ADR-0013 roadmap Phase 1): the pure, hardware-free half of the servo
driver — ``ServoAngles`` plus mechanical-limit clamping. The real I2C ``ServoDriver`` (the
HAT/PCA9685 I/O) is a follow-up once Phase 0 hardware bring-up picks a concrete SDK; nothing
here depends on that choice.
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
