"""Smoke test: the turret_sink package's public re-exports are importable from its root."""

from __future__ import annotations


def test_public_names_importable_from_package_root():
    from object_tracker import turret_sink

    for name in [
        "ActuatorSink",
        "AimCommand",
        "AimControllerState",
        "step",
        "select_target",
        "AimTransport",
        "UdpAimTransport",
        "encode",
    ]:
        assert hasattr(turret_sink, name), f"{name} not exported from turret_sink"
