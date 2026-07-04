"""Aim Controller (ADR-0013): pure P/PID step from pixel error to an Aim Command."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import AimGains


@dataclass(frozen=True)
class AimCommand:
    """A relative servo nudge (ADR-0013): ``pan_delta`` +right, ``tilt_delta`` +up."""

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
    """One axis of PID. Returns ``(clamped_output, new_integral, deadzone_applied_error)``."""
    error = 0.0 if abs(error) < gains.deadzone_px else error
    new_integral = integral + error * dt
    derivative = (error - prev_error) / dt if dt > 0 else 0.0
    output = gains.kp * error + gains.ki * new_integral + gains.kd * derivative
    clamped = max(-gains.max_delta_deg, min(gains.max_delta_deg, output))
    return clamped, new_integral, error


def step(
    error_px: tuple[float, float],
    gains: AimGains,
    prev_state: AimControllerState,
    dt: float,
) -> tuple[AimCommand, AimControllerState]:
    """Pure P (``ki == kd == 0``, Phase 3) / PID (Phase 4) step — same function, only the
    gains change between phases (ADR-0013).

    ``error_px`` is ``target_center - frame_center`` in image pixels: +x right, +y down.
    Pan follows +x directly. Tilt inverts the sign: image +y (target below centre) must
    drive the camera to look further down, which is ``AimCommand``'s *negative* tilt_delta
    (tilt_delta is +up) — the sign flip the spec's Risks section calls out as the classic
    first bug.
    """
    error_x, error_y = error_px
    pan, integral_x, prev_error_x = _pid_axis(
        error_x, gains, prev_state.integral_x, prev_state.prev_error_x, dt
    )
    tilt_raw, integral_y, prev_error_y = _pid_axis(
        error_y, gains, prev_state.integral_y, prev_state.prev_error_y, dt
    )
    command = AimCommand(pan_delta=pan, tilt_delta=-tilt_raw)
    new_state = AimControllerState(
        integral_x=integral_x,
        integral_y=integral_y,
        prev_error_x=prev_error_x,
        prev_error_y=prev_error_y,
    )
    return command, new_state
