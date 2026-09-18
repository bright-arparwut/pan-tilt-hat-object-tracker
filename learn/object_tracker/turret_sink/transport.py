"""Aim Transport (ADR-0013): the sole Mac-side network I/O, fire-and-forget UDP."""

from __future__ import annotations

import socket
from typing import Protocol

from .aim_controller import AimCommand
from .wire import encode


class AimTransport(Protocol):
    """Where an Aim Command goes. A Protocol so tests can capture commands without a socket."""

    def send(self, command: AimCommand) -> None: ...

    def close(self) -> None: ...


class UdpAimTransport:
    """Fire-and-forget UDP (ADR-0013).

    No ack, no retry. A dropped Aim Command is superseded by the next one ~30–60ms later, and
    **retrying a stale command is worse than dropping it** — it aims the turret at where the
    target used to be. That single sentence is why this is UDP and not TCP.

    Owns the monotonically increasing ``seq`` the Pi uses to drop stale datagrams.
    """

    def __init__(self, host: str, port: int) -> None:
        raise NotImplementedError("Week 10 — see learn/curriculum/week-10-wire-listener.md")

    def send(self, command: AimCommand) -> None:
        raise NotImplementedError("Week 10 — see learn/curriculum/week-10-wire-listener.md")

    def close(self) -> None:
        raise NotImplementedError("Week 10 — see learn/curriculum/week-10-wire-listener.md")
