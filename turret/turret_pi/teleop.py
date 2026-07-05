"""Phase-1 teleop harness (ADR-0013): drive the turret from the keyboard to calibrate the
axis-sign constants and pulse range before the tracking loop is closed. Hardware-only — the
pure key->delta mapping is unit-tested on the Mac; the interactive TTY loop is verified live
on the Pi. Run on the Pi with: ``python -m turret_pi.teleop``.
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
    Unknown keys return ``(0.0, 0.0)`` — a no-move."""
    pan_dir, tilt_dir = _KEY_DIRECTIONS.get(key.lower(), (0.0, 0.0))
    return (pan_dir * step_deg, tilt_dir * step_deg)


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
