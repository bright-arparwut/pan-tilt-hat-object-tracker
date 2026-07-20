"""Unit tests for the Mac-side wire encode (ADR-0013): one JSON object per UDP datagram."""

from __future__ import annotations

import json

import numpy as np

from object_tracker.turret_sink.aim_controller import AimCommand
from object_tracker.turret_sink.wire import encode


def test_encode_round_trips_through_json():
    payload = json.loads(encode(AimCommand(pan_delta=-2.3, tilt_delta=0.8), seq=1042))
    assert payload == {"pan_delta": -2.3, "tilt_delta": 0.8, "seq": 1042}


def test_encode_returns_bytes():
    assert isinstance(encode(AimCommand(0.0, 0.0), seq=1), bytes)


def test_encode_handles_numpy_float_command_fields():
    """Defense-in-depth: track centres arrive as numpy float32, so a stray numpy value can reach
    the wire. The hardware-facing encoder must yield valid JSON, not raise TypeError (ADR-0013)."""
    cmd = AimCommand(pan_delta=np.float32(-2.5), tilt_delta=np.float32(1.25))
    payload = json.loads(encode(cmd, seq=7))
    assert payload == {"pan_delta": -2.5, "tilt_delta": 1.25, "seq": 7}
    assert type(payload["pan_delta"]) is float
