"""Unit tests for UdpAimTransport (ADR-0013) — fire-and-forget UDP, no ack/retry.

The real socket is monkeypatched (mirrors how tests/test_sinks.py monkeypatches cv2) so no
network I/O happens in the test suite.
"""

from __future__ import annotations

import json

from object_tracker.turret_sink import transport
from object_tracker.turret_sink.aim_controller import AimCommand
from object_tracker.turret_sink.transport import UdpAimTransport


class FakeSocket:
    def __init__(self):
        self.sent: list[tuple[bytes, tuple]] = []
        self.closed = False

    def sendto(self, payload, addr):
        self.sent.append((payload, addr))

    def close(self):
        self.closed = True


def _patch_socket(monkeypatch) -> FakeSocket:
    fake = FakeSocket()
    monkeypatch.setattr(transport.socket, "socket", lambda *a, **k: fake)
    return fake


def test_send_increments_seq_each_call(monkeypatch):
    fake = _patch_socket(monkeypatch)
    t = UdpAimTransport("pi.local", 9000)

    t.send(AimCommand(1.0, 2.0))
    t.send(AimCommand(3.0, 4.0))

    seqs = [json.loads(payload)["seq"] for payload, _ in fake.sent]
    assert seqs == [1, 2]


def test_send_targets_the_configured_address(monkeypatch):
    fake = _patch_socket(monkeypatch)
    t = UdpAimTransport("pi.local", 9000)

    t.send(AimCommand(1.0, 2.0))

    _, addr = fake.sent[0]
    assert addr == ("pi.local", 9000)


def test_send_payload_matches_command(monkeypatch):
    fake = _patch_socket(monkeypatch)
    t = UdpAimTransport("pi.local", 9000)

    t.send(AimCommand(pan_delta=-1.5, tilt_delta=0.5))

    payload = json.loads(fake.sent[0][0])
    assert payload["pan_delta"] == -1.5
    assert payload["tilt_delta"] == 0.5


def test_close_closes_the_socket(monkeypatch):
    fake = _patch_socket(monkeypatch)
    UdpAimTransport("pi.local", 9000).close()
    assert fake.closed is True
