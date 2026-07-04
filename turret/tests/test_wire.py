from __future__ import annotations

import json

import pytest

from turret_pi.wire import decode


def test_decode_round_trips_a_valid_payload():
    payload = json.dumps({"pan_delta": -2.3, "tilt_delta": 0.8, "seq": 1042}).encode("utf-8")
    assert decode(payload) == (-2.3, 0.8, 1042)


def test_decode_raises_value_error_on_garbage_bytes():
    with pytest.raises(ValueError):
        decode(b"not json at all")


def test_decode_raises_value_error_on_missing_field():
    payload = json.dumps({"pan_delta": 1.0, "seq": 1}).encode("utf-8")  # tilt_delta missing
    with pytest.raises(ValueError):
        decode(payload)


def test_decode_raises_value_error_on_non_numeric_field():
    payload = json.dumps({"pan_delta": "abc", "tilt_delta": 0.0, "seq": 1}).encode("utf-8")
    with pytest.raises(ValueError):
        decode(payload)
