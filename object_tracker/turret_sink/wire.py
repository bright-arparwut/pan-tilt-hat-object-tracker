"""Wire protocol — Mac-side half (ADR-0013). One JSON object per UDP datagram:
``{"pan_delta": ..., "tilt_delta": ..., "seq": ...}``. No shared module with the Pi side
(ADR-0013: separate deployables/deps) — ``turret_pi.wire`` independently decodes the same
documented shape.
"""

from __future__ import annotations

import json

from .aim_controller import AimCommand


def encode(command: AimCommand, seq: int) -> bytes:
    """Encode one Aim Command as a UDP datagram payload.

    Coerces the deltas to plain ``float`` at this hardware-facing boundary: a numpy value
    (track centres are float32) would otherwise raise "not JSON serializable" and crash the
    control loop mid-run. The root fix lives in ``tracking._present_centers``; this is the
    belt-and-suspenders so a stray numpy type can never reach the wire (ADR-0013)."""
    payload = {
        "pan_delta": float(command.pan_delta),
        "tilt_delta": float(command.tilt_delta),
        "seq": seq,
    }
    return json.dumps(payload).encode("utf-8")
