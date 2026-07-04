"""Wire protocol — Mac-side half (ADR-0013). One JSON object per UDP datagram:
``{"pan_delta": ..., "tilt_delta": ..., "seq": ...}``. No shared module with the Pi side
(ADR-0013: separate deployables/deps) — ``turret_pi.wire`` independently decodes the same
documented shape.
"""

from __future__ import annotations

import json

from .aim_controller import AimCommand


def encode(command: AimCommand, seq: int) -> bytes:
    """Encode one Aim Command as a UDP datagram payload."""
    payload = {"pan_delta": command.pan_delta, "tilt_delta": command.tilt_delta, "seq": seq}
    return json.dumps(payload).encode("utf-8")
