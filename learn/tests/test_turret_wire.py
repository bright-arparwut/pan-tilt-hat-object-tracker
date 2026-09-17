"""Week 10 acceptance: the Mac-side encoder."""

from __future__ import annotations

import json

import numpy as np

from object_tracker.turret_sink.aim_controller import AimCommand
from object_tracker.turret_sink.wire import encode


def test_encode_produces_the_documented_json_shape():
    payload = encode(AimCommand(pan_delta=1.5, tilt_delta=-2.25), seq=42)
    assert json.loads(payload) == {"pan_delta": 1.5, "tilt_delta": -2.25, "seq": 42}


def test_encode_coerces_numpy_floats():
    """Belt and suspenders: a stray float32 here crashes a loop with a motor moving."""
    command = AimCommand(pan_delta=np.float32(1.5), tilt_delta=np.float32(-2.0))
    decoded = json.loads(encode(command, seq=1))
    assert decoded["pan_delta"] == 1.5
    assert type(decoded["pan_delta"]) is float
