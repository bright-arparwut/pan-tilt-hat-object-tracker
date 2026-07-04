"""Unit tests for the Target Selector (ADR-0013): pure lock-first-id policy.

No hardware, no YOLO — table-driven over synthetic present-id sets.
"""

from __future__ import annotations

import pytest

from object_tracker.turret_sink.target_selector import select_target


@pytest.mark.parametrize(
    "present_ids, prior_lock, expected",
    [
        (frozenset(), None, None),  # nothing present, never locked -> unlocked
        (frozenset(), 5, None),  # locked id vanished entirely -> unlocked (v1 holds position)
        (frozenset({3, 7}), None, 3),  # first lock: smallest present id (first-seen)
        (frozenset({3, 7}), 3, 3),  # keep the lock while it's present
        (frozenset({3, 7}), 7, 7),  # keep the *existing* lock even though 3 is also present
        (frozenset({3, 7}), 5, 3),  # old lock (5) gone -> re-latch smallest present
        (frozenset({9}), 3, 9),  # old lock (3) gone, only 9 present -> lock 9
    ],
)
def test_select_target(present_ids, prior_lock, expected):
    assert select_target(present_ids, prior_lock) == expected
