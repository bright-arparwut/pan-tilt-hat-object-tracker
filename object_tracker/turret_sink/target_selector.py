"""Target Selector (ADR-0013): pure lock-first-id policy — pick which Track the Actuator
Sink follows.
"""

from __future__ import annotations


def select_target(present_ids: frozenset[int], prior_lock: int | None) -> int | None:
    """Lock-first-id (ADR-0013): keep ``prior_lock`` while it's present; otherwise lock the
    smallest present id (ByteTrack ids are monotonic, so the smallest present id is the
    first-seen one — the same trick ``zoom.py``'s ``ZoomSlots`` uses). No ids present at all
    -> unlocked (``None``); the caller (``ActuatorSink``) holds position in that case rather
    than snapping anywhere (v1, ADR-0013)."""
    if not present_ids:
        return None
    if prior_lock is not None and prior_lock in present_ids:
        return prior_lock
    return min(present_ids)
