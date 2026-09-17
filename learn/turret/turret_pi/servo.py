"""Servo control (ADR-0013): both halves of the servo layer.

The pure, hardware-free half — ``ServoAngles`` plus mechanical-limit ``clamp_angles`` — comes
first, followed by the real I²C ``ServoDriver`` (PCA9685 I/O over an **injectable**
``adafruit`` ServoKit). Everything above the driver stays hardware-free and unit-testable on
the Mac; only ``ServoDriver`` touches the SDK, behind a lazy import reached solely when no kit
is injected.

Build it in that order. The pure half first means that by the time you plug anything in, the
only untested code is the SDK call itself.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Mechanical limits (deg) — MEASURE THESE ON YOUR OWN BUILD (week 9) ------------------
# The servos' *electrical* range is 0-180, but the assembled bracket's travel is narrower.
# Driving past a mechanical stop STALLS the motor: it strains, buzzes, draws a current spike
# that can brown out the Pi, and wears the gears. Software clamps every commanded angle so a
# stray command can't do that — but the limits must be measured first, with the teleop
# harness, on the platform you actually built.
#
# The values below are from the reference build. Re-measure yours and replace them.
PAN_MIN_DEG = 0.0
PAN_MAX_DEG = 180.0
TILT_MIN_DEG = 20.0   # bracket fouls the base below this
TILT_MAX_DEG = 115.0  # bracket hits the mount above this


@dataclass(frozen=True)
class ServoAngles:
    """An absolute pan/tilt pose in degrees."""

    pan_deg: float
    tilt_deg: float


def clamp_angles(angles: ServoAngles) -> ServoAngles:
    """Clamp both axes to the HAT's mechanical limits (pure, hardware-free).

    Return a *new* ``ServoAngles`` — never mutate. Five lines, and the thing standing between
    a software bug and a stripped servo gear.
    """
    raise NotImplementedError("Week 9 — see learn/curriculum/week-09-servos.md")


# --- Real I²C driver ---------------------------------------------------------------------
# The hardware-bound half: turns relative Aim Command nudges into absolute, clamped servo
# positions and writes them to the PCA9685. The only hardware-coupled unit in turret_pi.

PAN_CHANNEL = 0
TILT_CHANNEL = 1

# Startup/safe pose: the geometric mid-range of each axis's *measured* limits, so a fresh
# turret sits centred within its real travel rather than at a raw 90/90 that would tilt it
# hard toward one stop. Derive it — don't hardcode two numbers that drift from the limits.
CENTER = ServoAngles(
    pan_deg=(PAN_MIN_DEG + PAN_MAX_DEG) / 2.0,
    tilt_deg=(TILT_MIN_DEG + TILT_MAX_DEG) / 2.0,
)

# Per-servo calibration — measure with the teleop harness in week 9, then freeze.
SERVO_MIN_US = 500
SERVO_MAX_US = 2500
SERVO_ACTUATION_RANGE_DEG = 180.0
PAN_SIGN = +1.0   # +pan_delta (target right) -> which way pan_deg moves; flip if reversed
TILT_SIGN = +1.0  # +tilt_delta (target up)   -> which way tilt_deg moves; flip if reversed


class ServoDriver:
    """Real I²C driver for the Waveshare Pan-Tilt HAT (PCA9685).

    Implements the ``Servo`` Protocol the listener depends on. ``kit`` is **injectable** so
    the whole accumulate-clamp-write path is unit-testable on the Mac with a fake kit;
    ``kit=None`` constructs the real ``ServoKit`` behind a **lazy import**, which is what
    keeps this module importable on a machine with no ``adafruit-blinka`` installed.

    Set each channel's actuation range and pulse-width range at construction, then write the
    safe centre — so a freshly powered turret takes a known pose before accepting any command.
    """

    def __init__(self, kit=None, center: ServoAngles = CENTER) -> None:
        raise NotImplementedError("Week 9 — see learn/curriculum/week-09-servos.md")

    def _write(self, angles: ServoAngles) -> None:
        """Write an absolute pose to both channels and record it.

        Keep this as the **single write path**: every motion in the class goes through here,
        so there is exactly one place where "what the servo was told" is recorded. Replace
        ``self._current``, never mutate it.
        """
        raise NotImplementedError("Week 9 — see learn/curriculum/week-09-servos.md")

    def apply_delta(self, pan_delta: float, tilt_delta: float) -> None:
        """Accumulate a relative nudge onto the current pose, clamp, write both channels.

        Never raises on a large delta — the clamp is what makes that safe. A control loop
        must not be able to crash its own actuator with an out-of-range number.
        """
        raise NotImplementedError("Week 9 — see learn/curriculum/week-09-servos.md")

    def recenter(self) -> None:
        """Return to the safe centre (an absolute write, so it is sign-independent).

        Called on shutdown, to leave the turret in a known pose.
        """
        raise NotImplementedError("Week 9 — see learn/curriculum/week-09-servos.md")

    @property
    def current(self) -> ServoAngles:
        """Where the turret is pointing now (post-clamp)."""
        raise NotImplementedError("Week 9 — see learn/curriculum/week-09-servos.md")
