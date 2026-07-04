"""Aim Transport (ADR-0013): the sole Mac-side network I/O, fire-and-forget UDP."""

from __future__ import annotations

import socket
from typing import Protocol

from .aim_controller import AimCommand
from .wire import encode


class AimTransport(Protocol):
    def send(self, command: AimCommand) -> None: ...

    def close(self) -> None: ...


class UdpAimTransport:
    """Fire-and-forget UDP (ADR-0013): a dropped Aim Command is superseded by the next one
    ~30-60ms later, so there is no ack/retry — retrying a stale command is worse than
    dropping it."""

    def __init__(self, host: str, port: int) -> None:
        self._addr = (host, port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._seq = 0

    def send(self, command: AimCommand) -> None:
        self._seq += 1
        self._sock.sendto(encode(command, self._seq), self._addr)

    def close(self) -> None:
        self._sock.close()
