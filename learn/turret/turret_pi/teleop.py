"""Teleop harness (ADR-0013): drive the turret from the keyboard to calibrate the axis-sign
constants and the mechanical limits before the tracking loop is closed.

Run on the Pi with ``python -m turret_pi.teleop``. This is the tool you use in week 9 to
*measure* the four ``*_MIN_DEG``/``*_MAX_DEG`` constants and to discover, immediately and
cheaply, that one of your axes moves the wrong way.

The pure key→delta mapping is Mac-testable; the interactive TTY loop is given (it is termios
plumbing, not a lesson) and can only be verified live on the Pi.
"""

from __future__ import annotations

import sys
import termios
import tty

from .servo import ServoDriver

STEP_DEG = 5.0

# WASD -> unit direction (pan, tilt); scaled by step_deg. Matches the wire contract:
# +pan_delta = target right, +tilt_delta = target up (ADR-0013).
_KEY_DIRECTIONS: dict[str, tuple[float, float]] = {
    "w": (0.0, +1.0),   # tilt up
    "s": (0.0, -1.0),   # tilt down
    "a": (-1.0, 0.0),   # pan left
    "d": (+1.0, 0.0),   # pan right
}


def key_to_delta(key: str, step_deg: float = STEP_DEG) -> tuple[float, float]:
    """Map a WASD keystroke to a ``(pan_delta, tilt_delta)`` nudge in degrees (pure).

    Unknown keys return ``(0.0, 0.0)`` — a no-move. Case-insensitive: caps lock should not
    disable your calibration tool.
    """
    raise NotImplementedError("Week 9 — see learn/curriculum/week-09-servos.md")


# --- GIVEN: the interactive TTY loop (termios plumbing, not a lesson) --------------------
def run_teleop(driver: ServoDriver) -> None:  # pragma: no cover - interactive/hardware
    """Read single keystrokes from stdin and nudge the driver until ``q``. Prints the pose
    after each move so the operator can read off the sign and range calibration."""
    fd = sys.stdin.fileno()
    original = termios.tcgetattr(fd)
    print("teleop: WASD to nudge, q to quit")
    try:
        tty.setcbreak(fd)
        while True:
            key = sys.stdin.read(1)
            if key == "q":
                break
            pan_delta, tilt_delta = key_to_delta(key)
            if (pan_delta, tilt_delta) != (0.0, 0.0):
                driver.apply_delta(pan_delta, tilt_delta)
                pose = driver.current
                print(f"  pan={pose.pan_deg:.1f}  tilt={pose.tilt_deg:.1f}")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original)


def main() -> int:  # pragma: no cover - hardware entrypoint
    run_teleop(ServoDriver())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
