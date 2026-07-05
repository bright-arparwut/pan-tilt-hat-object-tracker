"""Command listener (ADR-0013 roadmap Phase 3): the Pi-side UDP receive loop.

Receives Aim Command datagrams from the Mac, drops the malformed and the stale, and nudges
the servo. Split the repo's usual way — a **pure per-datagram core** (`handle_datagram`,
testable with a fake servo and zero sockets) wrapped in a **thin blocking I/O loop**
(`run_listener`). The loop owns only the socket; every decision lives in the pure core.

Depends on a `Servo` *Protocol*, not the concrete `ServoDriver`, so the listener stays
hardware-free and fully unit-testable (the real driver's I²C/HAT SDK is still an open Phase 1
item — see the design spec). `main.py` will inject the real `ServoDriver`.

Security note (ADR-0013 trust model): this is an *unauthenticated* UDP control plane — any
host that can reach the port can drive the servo. That is an accepted v1 trade-off for a
trusted, isolated LAN. `run_listener` offers two cheap defense-in-depth controls — a
configurable bind `host` (don't listen on all interfaces if you don't have to) and an
`allowed_source` IP filter — but neither is real authentication (UDP source IPs are spoofable
by an on-path attacker). A signed datagram (HMAC over the payload + a shared key) is the proper
fix and should land before this drives anything dangerous.
"""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from .wire import decode

# A datagram is one small JSON object; 4 KiB is comfortably larger than any Aim Command.
_MAX_DATAGRAM = 4096

# A quiet gap longer than this (no *applied* command) ends the current command session: the
# next datagram is then accepted regardless of its seq. Freshest-command-wins (drop seq <=
# last_seq) is only meaningful *within* one live session; across a session boundary — the Mac
# tracker restarting (its seq resets to 1) or a one-off bogus high-seq packet — a monotonic-only
# filter would wedge the turret forever. Because a dropped command never refreshes last_ts, a
# wedge self-heals SESSION_GAP_S after the last applied command (ADR-0013).
SESSION_GAP_S = 1.0


class Servo(Protocol):
    """The only thing the listener needs from the servo driver: apply a relative nudge."""

    def apply_delta(self, pan_delta: float, tilt_delta: float) -> None: ...


@dataclass(frozen=True)
class ListenerState:
    """Threaded loop state: the highest seq applied in the current session, and the monotonic
    time it was applied (the session clock). Both default to 0 — the first real datagram is
    always fresh (seq >= 1 > 0, and/or the default session is already stale).
    """

    last_seq: int = 0
    last_ts: float = 0.0


def handle_datagram(
    payload: bytes, servo: Servo, state: ListenerState, now: float
) -> ListenerState:
    """Pure per-datagram core: decode → drop malformed/stale → ``servo.apply_delta``.

    ``now`` is a monotonic timestamp (the loop passes ``time.monotonic()``); it is an argument,
    not read here, so the function stays pure and testable. Returns the next state.

    A malformed datagram (``decode`` raises) is dropped, state unchanged. Otherwise the command
    is applied unless it is **stale within the current session** — i.e. ``seq <= last_seq`` *and*
    less than ``SESSION_GAP_S`` has passed since the last applied command. Dropping a stale
    in-session command is deliberate: UDP can reorder, and re-aiming to an *older* target
    position is worse than waiting for the next command ~30–60 ms later. But once the session
    goes quiet (a restart, or a wedge from a bogus high seq), the seq gate is dropped so the loop
    re-latches instead of ignoring the sender forever (ADR-0013)."""
    try:
        pan_delta, tilt_delta, seq = decode(payload)
    except ValueError:
        return state  # malformed → drop, one bad packet never crashes the loop
    within_session = (now - state.last_ts) <= SESSION_GAP_S
    if within_session and seq <= state.last_seq:
        return state  # stale / duplicate within the live session → drop
    servo.apply_delta(pan_delta, tilt_delta)
    return ListenerState(last_seq=seq, last_ts=now)


def run_listener(
    servo: Servo,
    port: int | None = None,
    *,
    host: str = "0.0.0.0",
    sock: socket.socket | None = None,
    allowed_source: str | None = None,
    should_continue: Callable[[], bool] = lambda: True,
    recv_timeout: float = 0.5,
) -> None:
    """Blocking UDP loop: receive → ``handle_datagram`` → repeat until ``should_continue()``
    is False (default: forever — the deploy runs it under systemd).

    Binds a UDP socket on ``host:port`` unless one is injected via ``sock`` (the seam the tests
    use to bind an ephemeral port and know where to send). ``host`` defaults to ``0.0.0.0`` (all
    interfaces) for LAN convenience — restrict it if the Pi has an interface you don't want the
    control plane on. ``allowed_source``, when set, drops any datagram whose source IP differs —
    cheap defense-in-depth, **not** authentication (UDP source IPs are spoofable). A short
    ``recv_timeout`` makes the loop poll ``should_continue`` rather than block on ``recvfrom``
    forever, so it can be stopped cleanly.

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
            sock.bind((host, port))  # failure here still closes sock via the finally
        while should_continue():
            try:
                payload, addr = sock.recvfrom(_MAX_DATAGRAM)
            except socket.timeout:
                continue  # no datagram this window — re-check should_continue and wait again
            if allowed_source is not None and addr[0] != allowed_source:
                continue  # not from the expected sender — defense-in-depth, not auth
            state = handle_datagram(payload, servo, state, time.monotonic())
    finally:
        if own_socket:
            sock.close()
