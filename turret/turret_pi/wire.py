"""Wire protocol — Pi-side half (ADR-0013). Decodes the same JSON-per-UDP-datagram shape
``object_tracker.turret_sink.wire.encode`` produces. No shared module between Mac and Pi
(separate deployables/deps) — this is an independent decode of the documented shape, not an
import of the Mac-side encoder.
"""

from __future__ import annotations

import json


def decode(payload: bytes) -> tuple[float, float, int]:
    """Decode one Aim Command datagram to ``(pan_delta, tilt_delta, seq)``.

    Raises ``ValueError`` on anything that isn't the documented shape (malformed JSON,
    missing/non-numeric fields) — the caller (the future ``listener.run_listener``) drops
    such a datagram rather than propagating a crash from a single bad packet.
    """
    try:
        obj = json.loads(payload)
        return float(obj["pan_delta"]), float(obj["tilt_delta"]), int(obj["seq"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"malformed aim command payload: {payload!r}") from exc
