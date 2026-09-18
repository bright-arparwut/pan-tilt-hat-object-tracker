"""Target Selector (ADR-0013): pure lock-first-id policy — pick which Track the Actuator
Sink follows.
"""

from __future__ import annotations


def select_target(present_ids: frozenset[int], prior_lock: int | None) -> int | None:
    """Lock-first-id (ADR-0013).

    Keep ``prior_lock`` while it is present. Otherwise lock the **smallest** present id —
    tracker ids are monotonic, so the smallest present id is the first-seen one (the same
    trick ``zoom.ZoomSlots`` uses in week 7). No ids present at all → unlocked (``None``);
    the caller holds position rather than snapping anywhere.

    Deterministic by design: a policy like "follow the largest box" or "follow the highest
    confidence" re-decides every frame and makes the turret twitch between targets.
    """
    raise NotImplementedError("Week 11 — see learn/curriculum/week-11-visual-servoing.md")
