"""Week 7 acceptance: the identity-slot state machine.

Note there is not a single numpy array in this file. The slot logic is a decision machine;
if testing it needs pixels, the split is in the wrong place.
"""

from __future__ import annotations

from object_tracker.zoom import ZoomSlots


def _slot_of(renders, track_id):
    return next((r.index for r in renders if r.track_id == track_id), None)


def test_a_track_keeps_its_slot_across_frames():
    slots = ZoomSlots(max_slots=2, buffer=5)
    renders = slots.update({7: (10.0, 10.0), 9: (20.0, 20.0)}, 0)
    seven, nine = _slot_of(renders, 7), _slot_of(renders, 9)
    assert {seven, nine} == {0, 1}

    for frame_idx in range(1, 4):
        renders = slots.update({9: (21.0, 21.0), 7: (11.0, 11.0)}, frame_idx)
        assert _slot_of(renders, 7) == seven, "the strip must never reflow"
        assert _slot_of(renders, 9) == nine


def test_a_missing_track_holds_its_slot_black_for_the_buffer():
    slots = ZoomSlots(max_slots=2, buffer=5)
    slots.update({7: (10.0, 10.0)}, 0)
    renders = slots.update({}, 2)
    held = next(r for r in renders if r.track_id == 7)
    assert held.center is None, "a lost-but-alive Track draws black in place"
    assert held.index == 0


def test_a_slot_is_freed_for_a_new_track_after_the_hold_elapses():
    slots = ZoomSlots(max_slots=1, buffer=5)
    slots.update({7: (10.0, 10.0)}, 0)
    renders = slots.update({99: (30.0, 30.0)}, 20)   # 20 - 0 > buffer
    assert _slot_of(renders, 7) is None
    assert _slot_of(renders, 99) == 0


def test_forced_track_id_pins_the_only_slot():
    slots = ZoomSlots(max_slots=4, buffer=5, forced_id=9)
    assert slots.capacity == 1
    renders = slots.update({7: (10.0, 10.0), 9: (20.0, 20.0)}, 0)
    assert [r.track_id for r in renders] == [9]
