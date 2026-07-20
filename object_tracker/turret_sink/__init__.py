"""turret_sink — the Mac-side Actuator Sink for the pan-tilt tracking turret (ADR-0013).

Re-exports the package's public surface: pure Target Selector / Aim Controller units, the
UDP wire encode + transport, and the ActuatorSink FrameSink that glues them together.
"""

from __future__ import annotations

from .actuator_sink import ActuatorSink
from .aim_controller import AimCommand, AimControllerState, step
from .target_selector import select_target
from .transport import AimTransport, UdpAimTransport
from .wire import encode

__all__ = [
    "ActuatorSink",
    "AimCommand",
    "AimControllerState",
    "step",
    "select_target",
    "AimTransport",
    "UdpAimTransport",
    "encode",
]
