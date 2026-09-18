"""Week 10 acceptance: the pure per-datagram core. No sockets, no sleeps, no real clock."""

from __future__ import annotations

import json

from turret_pi.listener import SESSION_GAP_S, ListenerState, handle_datagram


class _FakeServo:
    def __init__(self):
        self.applied = []

    def apply_delta(self, pan_delta, tilt_delta):
        self.applied.append((pan_delta, tilt_delta))


def _datagram(pan=1.0, tilt=2.0, seq=1):
    return json.dumps({"pan_delta": pan, "tilt_delta": tilt, "seq": seq}).encode()


def test_a_malformed_datagram_is_dropped_without_touching_the_servo():
    servo = _FakeServo()
    state = ListenerState()
    assert handle_datagram(b"garbage", servo, state, now=100.0) == state
    assert servo.applied == []


def test_a_stale_seq_within_the_session_is_dropped():
    """UDP reorders. Re-aiming at where the target *was* is worse than waiting 30ms."""
    servo = _FakeServo()
    state = handle_datagram(_datagram(seq=5), servo, ListenerState(), now=100.0)
    state = handle_datagram(_datagram(seq=3), servo, state, now=100.1)
    assert len(servo.applied) == 1, "the out-of-order datagram must not move the servo"


def test_the_seq_gate_is_dropped_after_a_quiet_gap_so_a_restarted_sender_relatches():
    """Without this, a Mac restart (seq resets to 1) wedges the turret forever."""
    servo = _FakeServo()
    state = handle_datagram(_datagram(seq=5000), servo, ListenerState(), now=100.0)
    later = 100.0 + SESSION_GAP_S + 0.5
    handle_datagram(_datagram(seq=1), servo, state, now=later)
    assert len(servo.applied) == 2, "past the session gap, a low seq must be accepted again"
