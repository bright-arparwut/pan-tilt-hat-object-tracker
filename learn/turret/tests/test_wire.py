"""Week 10 acceptance: the Pi-side decoder."""

from __future__ import annotations

import json

import pytest

from turret_pi.wire import decode


def test_decode_reads_the_documented_shape():
    payload = json.dumps({"pan_delta": 1.5, "tilt_delta": -2.0, "seq": 7}).encode()
    assert decode(payload) == (1.5, -2.0, 7)


@pytest.mark.parametrize(
    "payload",
    [
        b"not json at all",
        b"{}",
        json.dumps({"pan_delta": 1.0, "tilt_delta": 2.0}).encode(),      # missing seq
        json.dumps({"pan_delta": "x", "tilt_delta": 2.0, "seq": 1}).encode(),
    ],
)
def test_decode_rejects_malformed_payloads(payload):
    """One bad packet, from anywhere on the network, must never crash a motor loop."""
    with pytest.raises(ValueError):
        decode(payload)
