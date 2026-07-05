from __future__ import annotations

import json
import socket
import threading
import time
from unittest import mock

import pytest

from turret_pi.listener import ListenerState, handle_datagram, run_listener


class FakeServo:
    """Records apply_delta calls so the pure/loop logic is testable with no HAT (ADR-0013)."""

    def __init__(self) -> None:
        self.calls: list[tuple[float, float]] = []

    def apply_delta(self, pan_delta: float, tilt_delta: float) -> None:
        self.calls.append((pan_delta, tilt_delta))


def _datagram(pan: float, tilt: float, seq: int) -> bytes:
    return json.dumps({"pan_delta": pan, "tilt_delta": tilt, "seq": seq}).encode("utf-8")


# --- handle_datagram: the pure per-datagram core ---------------------------------------


def test_fresh_command_is_applied_and_advances_last_seq():
    servo = FakeServo()
    state = handle_datagram(_datagram(1.5, -2.0, 1), servo, ListenerState())
    assert servo.calls == [(1.5, -2.0)]
    assert state == ListenerState(last_seq=1)


def test_malformed_payload_is_dropped_and_state_unchanged():
    servo = FakeServo()
    prior = ListenerState(last_seq=7)
    state = handle_datagram(b"not json at all", servo, prior)
    assert servo.calls == []
    assert state == prior


def test_stale_seq_is_dropped():
    servo = FakeServo()
    prior = ListenerState(last_seq=10)
    state = handle_datagram(_datagram(1.0, 1.0, 3), servo, prior)  # 3 <= 10
    assert servo.calls == []
    assert state == prior


def test_duplicate_seq_is_dropped():
    servo = FakeServo()
    prior = ListenerState(last_seq=5)
    state = handle_datagram(_datagram(1.0, 1.0, 5), servo, prior)  # 5 <= 5
    assert servo.calls == []
    assert state == prior


def test_out_of_order_older_datagram_is_dropped_but_newer_still_applies():
    servo = FakeServo()
    state = ListenerState()
    state = handle_datagram(_datagram(1.0, 0.0, 5), servo, state)  # applied
    state = handle_datagram(_datagram(9.0, 9.0, 3), servo, state)  # stale, dropped
    state = handle_datagram(_datagram(2.0, 0.0, 6), servo, state)  # applied
    assert servo.calls == [(1.0, 0.0), (2.0, 0.0)]
    assert state == ListenerState(last_seq=6)


def test_monotonic_stream_all_applied():
    servo = FakeServo()
    state = ListenerState()
    for seq in range(1, 5):
        state = handle_datagram(_datagram(float(seq), 0.0, seq), servo, state)
    assert servo.calls == [(1.0, 0.0), (2.0, 0.0), (3.0, 0.0), (4.0, 0.0)]
    assert state == ListenerState(last_seq=4)


# --- run_listener: the thin I/O loop over a real loopback socket -----------------------


def test_run_listener_applies_datagrams_from_a_real_socket_then_stops():
    servo = FakeServo()
    # Bind our own socket to an ephemeral port so tests never collide on a fixed port; hand
    # it to run_listener so we know exactly where to send.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]

    stop = threading.Event()
    thread = threading.Thread(
        target=run_listener,
        args=(servo,),
        kwargs={"sock": sock, "should_continue": lambda: not stop.is_set(), "recv_timeout": 0.05},
    )
    thread.start()
    try:
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender.sendto(_datagram(1.0, -1.0, 1), ("127.0.0.1", port))
        sender.sendto(b"garbage", ("127.0.0.1", port))  # dropped
        sender.sendto(_datagram(2.0, -2.0, 2), ("127.0.0.1", port))
        sender.close()
        # Drain the datagrams under a hard 2s deadline so a lost loopback packet fails loudly
        # instead of hanging the suite (the finally still stops + joins the thread either way).
        deadline = time.monotonic() + 2.0
        while len(servo.calls) < 2 and time.monotonic() < deadline:
            if not thread.is_alive():
                break
            time.sleep(0.02)
    finally:
        stop.set()
        thread.join(timeout=2.0)

    assert not thread.is_alive()
    assert servo.calls == [(1.0, -1.0), (2.0, -2.0)]


def test_run_listener_binds_and_closes_a_socket_it_owns():
    servo = FakeServo()
    with mock.patch("turret_pi.listener.socket.socket") as socket_factory:
        fake_sock = socket_factory.return_value
        # should_continue False from the start: the loop never enters recvfrom, but setup +
        # teardown (bind, then close in the finally) must still run for a socket it owns.
        run_listener(servo, port=9000, should_continue=lambda: False, recv_timeout=0.05)
    fake_sock.bind.assert_called_once_with(("0.0.0.0", 9000))
    fake_sock.close.assert_called_once()


def test_run_listener_does_not_close_an_injected_socket():
    servo = FakeServo()
    fake_sock = mock.Mock()
    run_listener(servo, sock=fake_sock, should_continue=lambda: False)
    fake_sock.bind.assert_not_called()  # caller already bound it
    fake_sock.close.assert_not_called()  # caller owns its lifecycle


def test_run_listener_requires_a_port_when_no_socket_injected():
    with pytest.raises(ValueError):
        run_listener(FakeServo())
