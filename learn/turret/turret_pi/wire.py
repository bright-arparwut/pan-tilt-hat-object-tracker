"""Wire protocol — Pi-side half (ADR-0013).

Decodes the same JSON-per-UDP-datagram shape ``object_tracker.turret_sink.wire.encode``
produces. **No shared module between Mac and Pi** — separate deployables, separate dependency
trees. This is an independent decode of a documented shape, not an import of the encoder.
"""

from __future__ import annotations

import json


def decode(payload: bytes) -> tuple[float, float, int]:
    """Decode one Aim Command datagram to ``(pan_delta, tilt_delta, seq)``.

    Raise ``ValueError`` on anything that isn't the documented shape — malformed JSON, a
    missing field, a non-numeric value. The caller (``listener.handle_datagram``) **drops**
    such a datagram rather than propagating a crash: one bad packet, from anywhere on the
    network, must never take down a loop that is driving a motor.

    Include the offending payload in the message. You will be glad of it at 11pm.
    """
    raise NotImplementedError("Week 10 — see learn/curriculum/week-10-wire-listener.md")
