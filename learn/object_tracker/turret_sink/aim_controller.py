"""Aim Controller (ADR-0013): pure P/PID step from pixel error to an Aim Command."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import AimGains


@dataclass(frozen=True)
class AimCommand:
    """A relative servo nudge (ADR-0013): ``pan_delta`` +right, ``tilt_delta`` **+up**."""

    pan_delta: float
    tilt_delta: float


@dataclass(frozen=True)
class AimControllerState:
    """Threaded PID state — one integral/previous-error pair per axis."""

    integral_x: float = 0.0
    integral_y: float = 0.0
    prev_error_x: float = 0.0
    prev_error_y: float = 0.0


def _pid_axis(
    error: float, gains: AimGains, integral: float, prev_error: float, dt: float
) -> tuple[float, float, float]:
    """One axis of PID. Returns ``(clamped_output, new_integral, deadzone_applied_error)``.

    In order: apply the **deadzone** (|error| below ``deadzone_px`` becomes exactly 0, which
    is what stops the turret hunting noise at rest), accumulate the **integral**, compute the
    **derivative** (guard ``dt == 0`` — a division by zero here crashes a loop that is
    driving a motor), combine with the gains, then **clamp** to ``±max_delta_deg``.

    The deadzoned error — not the raw one — is what gets threaded out as the next step's
    ``prev_error``. Think about what the derivative term would do otherwise.
    """
    raise NotImplementedError("Week 11 — see learn/curriculum/week-11-visual-servoing.md")


def step(
    error_px: tuple[float, float],
    gains: AimGains,
    prev_state: AimControllerState,
    dt: float,
) -> tuple[AimCommand, AimControllerState]:
    """Pure P (``ki == kd == 0``) / PID step — same function, only the gains change.

    ``error_px`` is ``target_center - frame_center`` in image pixels: **+x right, +y down**.

    Pan follows +x directly. **Tilt inverts the sign**: image +y means the target is *below*
    centre, which must drive the camera to look further *down*, and ``AimCommand.tilt_delta``
    is **+up**. So ``tilt_delta = -(pid output for error_y)``.

    That sign flip is the classic first bug on this project. Get it wrong and the turret runs
    away to its limit within a second, because every correction makes the error larger. There
    is a given test for exactly this; do not skip it.
    """
    raise NotImplementedError("Week 11 — see learn/curriculum/week-11-visual-servoing.md")
