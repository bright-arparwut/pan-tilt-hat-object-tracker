"""Week 11 acceptance: the glue. Every decision is tested elsewhere; this is wiring."""

from __future__ import annotations

import numpy as np
import supervision as sv

from object_tracker.config import AimGains
from object_tracker.turret_sink.actuator_sink import ActuatorSink


class _CapturingTransport:
    def __init__(self):
        self.sent = []
        self.closed = False

    def send(self, command):
        self.sent.append(command)

    def close(self):
        self.closed = True


def _tracks(track_id, cx, cy):
    return sv.Detections(
        xyxy=np.asarray([[cx - 5, cy - 5, cx + 5, cy + 5]], dtype=float),
        confidence=np.asarray([0.9]),
        class_id=np.asarray([0]),
        tracker_id=np.asarray([track_id]),
    )


def _sink(transport, **kw):
    gains = AimGains(kp=0.1, ki=0.0, kd=0.0, deadzone_px=1.0, max_delta_deg=10.0)
    return ActuatorSink(transport, gains, (640, 480), **kw)


def test_show_always_returns_true():
    """An actuator never asks the loop to stop — it has no opinion about the run ending."""
    transport = _CapturingTransport()
    sink = _sink(transport)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert sink.show(frame, _tracks(1, 400.0, 240.0)) is True
    assert sink.show(frame, None) is True


def test_a_target_right_of_centre_commands_a_positive_pan():
    transport = _CapturingTransport()
    sink = _sink(transport)
    clock = iter([0.0, 0.1])
    sink._clock = lambda: next(clock)  # type: ignore[method-assign]
    sink.show(np.zeros((480, 640, 3), dtype=np.uint8), _tracks(1, 500.0, 240.0))
    assert transport.sent, "a locked target must ship a command"
    assert transport.sent[-1].pan_delta > 0


def test_close_closes_the_transport():
    transport = _CapturingTransport()
    _sink(transport).close()
    assert transport.closed
