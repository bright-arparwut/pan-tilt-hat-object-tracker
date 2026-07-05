"""Command listener (ADR-0013 roadmap Phase 3): the Pi-side UDP receive loop.

Receives Aim Command datagrams from the Mac, drops the malformed and the stale, and nudges
the servo. Split the repo's usual way — a **pure per-datagram core** (`handle_datagram`,
testable with a fake servo and zero sockets) wrapped in a **thin blocking I/O loop**
(`run_listener`). The loop owns only the socket; every decision lives in the pure core.

Depends on a `Servo` *Protocol*, not the concrete `ServoDriver`, so the listener stays
hardware-free and fully unit-testable (the real driver's I²C/HAT SDK is still an open Phase 1
item — see the design spec). `main.py` will inject the real `ServoDriver`.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Callable, Protocol

from .wire import decode

# A datagram is one small JSON object; 4 KiB is comfortably larger than any Aim Command.
_MAX_DATAGRAM = 4096


class Servo(Protocol):
    """The only thing the listener needs from the servo driver: apply a relative nudge."""

    def apply_delta(self, pan_delta: float, tilt_delta: float) -> None: ...


@dataclass(frozen=True)
class ListenerState:
    """Threaded loop state — the highest seq applied so far (freshest-command-wins).

    Init 0 because the Mac's ``UdpAimTransport`` emits seq starting at 1, so the first real
    datagram (seq 1) is always fresh against the default.
    """

    last_seq: int = 0


def handle_datagram(payload: bytes, servo: Servo, state: ListenerState) -> ListenerState:
    """Pure per-datagram core: decode → drop malformed/stale → ``servo.apply_delta``.

    Returns the next state. A malformed datagram (``decode`` raises) or a stale/duplicate one
    (``seq <= last_seq``, an out-of-order or resent packet) is dropped and leaves the state
    unchanged; only a fresh, valid command applies and advances ``last_seq``. Dropping a stale
    command is deliberate — UDP can reorder, and re-aiming to an *older* target position is
    worse than doing nothing until the next command arrives ~30–60 ms later (ADR-0013).
    """
    try:
        pan_delta, tilt_delta, seq = decode(payload)
    except ValueError:
        return state  # malformed → drop, one bad packet never crashes the loop
    if seq <= state.last_seq:
        return state  # stale / duplicate → drop
    servo.apply_delta(pan_delta, tilt_delta)
    return ListenerState(last_seq=seq)


def run_listener(
    servo: Servo,
    port: int | None = None,
    *,
    sock: socket.socket | None = None,
    should_continue: Callable[[], bool] = lambda: True,
    recv_timeout: float = 0.5,
) -> None:
    """Blocking UDP loop: receive → ``handle_datagram`` → repeat until ``should_continue()``
    is False (default: forever — the deploy runs it under systemd).

    Binds a UDP socket on ``port`` (``0.0.0.0``) unless one is injected via ``sock`` (the seam
    the tests use to bind an ephemeral port and know where to send). A short ``recv_timeout``
    makes the loop poll ``should_continue`` rather than block on ``recvfrom`` forever, so it can
    be stopped cleanly.

    Ownership: a socket the loop *creates* here is bound and closed by the loop, and is closed
    even if ``bind`` fails (no leaked fd on ``Address already in use`` — the common fast-restart
    failure under systemd). An injected socket is never closed here, but note ``recv_timeout`` is
    still applied to it (``settimeout`` is overwritten) — pass a socket you are not concurrently
    using elsewhere. Passing both ``sock`` and ``port`` ignores ``port``.
    """
    own_socket = sock is None
    if own_socket and port is None:
        raise ValueError("run_listener needs a port when no socket is injected")
    if own_socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    state = ListenerState()
    try:
        sock.settimeout(recv_timeout)
        if own_socket:
            sock.bind(("0.0.0.0", port))  # failure here still closes sock via the finally
        while should_continue():
            try:
                payload, _addr = sock.recvfrom(_MAX_DATAGRAM)
            except socket.timeout:
                continue  # no datagram this window — re-check should_continue and wait again
            state = handle_datagram(payload, servo, state)
    finally:
        if own_socket:
            sock.close()
