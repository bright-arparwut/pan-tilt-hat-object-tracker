"""Unit tests for the Mac-side wire encode (ADR-0013): one JSON object per UDP datagram."""

from __future__ import annotations

import json

from object_tracker.turret_sink.aim_controller import AimCommand
from object_tracker.turret_sink.wire import encode


def test_encode_round_trips_through_json():
    payload = json.loads(encode(AimCommand(pan_delta=-2.3, tilt_delta=0.8), seq=1042))
    assert payload == {"pan_delta": -2.3, "tilt_delta": 0.8, "seq": 1042}


def test_encode_returns_bytes():
    assert isinstance(encode(AimCommand(0.0, 0.0), seq=1), bytes)
