"""Command listener (ADR-0013): the Pi-side UDP receive loop.

Receives Aim Command datagrams from the Mac, drops the malformed and the stale, and nudges
the servo. Split the project's usual way — a **pure per-datagram core** (``handle_datagram``,
testable with a fake servo and zero sockets) wrapped in a **thin blocking I/O loop**
(``run_listener``). The loop owns only the socket; every decision lives in the pure core.

**This is the best example of the project's spine. Study the split before you write it.**

Depends on a ``Servo`` *Protocol*, not the concrete ``ServoDriver``, so the listener stays
hardware-free and fully unit-testable on the Mac.

Security note (ADR-0013 trust model): this is an **unauthenticated** UDP control plane — any
host that can reach the port can drive the servo. That is an accepted v1 trade-off for a
trusted, isolated LAN. ``run_listener`` offers two cheap defence-in-depth controls — a
configurable bind ``host`` and an ``allowed_source`` IP filter — but **neither is
authentication**: UDP source IPs are spoofable by an on-path attacker. A signed datagram
(HMAC over the payload + a shared key) is the proper fix and should land before this drives
anything dangerous. Writing the limitation down honestly is part of the design.
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
# next datagram is then accepted regardless of its seq.
#
# Why this exists: freshest-command-wins (drop seq <= last_seq) is only meaningful *within*
# one live session. Across a session boundary — the Mac tracker restarting, so its seq resets
# to 1, or a single bogus high-seq packet — a monotonic-only filter would wedge the turret
# FOREVER. Because a dropped command never refreshes last_ts, a wedge self-heals this many
# seconds after the last *applied* command. Make sure you see why that second sentence is
# what makes it work.
SESSION_GAP_S = 1.0


class Servo(Protocol):
    """The only thing the listener needs from the servo driver: apply a relative nudge."""

    def apply_delta(self, pan_delta: float, tilt_delta: float) -> None: ...


@dataclass(frozen=True)
class ListenerState:
    """Threaded loop state: the highest seq applied in the current session, and the monotonic
    time it was applied (the session clock). Both default to 0 — so the first real datagram is
    always fresh (seq >= 1 > 0, and the default session is already stale).
    """

    last_seq: int = 0
    last_ts: float = 0.0


def handle_datagram(
    payload: bytes, servo: Servo, state: ListenerState, now: float
) -> ListenerState:
    """Pure per-datagram core: decode → drop malformed/stale → ``servo.apply_delta``.

    ``now`` is a monotonic timestamp passed **in** as an argument, never read here. That one
    choice is what makes every staleness rule testable without sockets, sleeps, or a clock.

    The rules:
      * Malformed (``decode`` raises) → drop, state unchanged.
      * **Stale within the current session** — ``seq <= last_seq`` *and* less than
        ``SESSION_GAP_S`` since the last applied command → drop. UDP reorders, and re-aiming
        to an *older* target position is worse than waiting ~30-60ms for the next command.
      * Otherwise → apply, and record the new seq and time.

    Once the session goes quiet, the seq gate drops entirely so the loop re-latches rather
    than ignoring the sender forever.
    """
    raise NotImplementedError("Week 10 — see learn/curriculum/week-10-wire-listener.md")


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
    is False.

    Binds a UDP socket on ``host:port`` unless one is injected via ``sock`` — that injection
    is the seam the tests use to bind an ephemeral port and know where to send.

    A short ``recv_timeout`` makes the loop **poll** ``should_continue`` rather than block on
    ``recvfrom`` forever, so it can be stopped cleanly. Without it, SIGTERM leaves the process
    hanging in a syscall.

    **Socket ownership** — get this right, it is a real bug source:
      * A socket the loop *creates* is bound and closed by the loop, and is closed **even if
        ``bind`` raises** — no leaked fd on "Address already in use", which is the common
        fast-restart failure under systemd.
      * An *injected* socket is never closed here. (But note ``recv_timeout`` is still applied
        to it, so don't pass a socket you are using concurrently elsewhere.)
    """
    raise NotImplementedError("Week 10 — see learn/curriculum/week-10-wire-listener.md")
