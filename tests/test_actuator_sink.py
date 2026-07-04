"""Unit tests for ActuatorSink (ADR-0013) — the FrameSink that aims the turret.

Uses a fake AimTransport double (mirrors FakeSink in tests/test_sinks.py) so no real
socket/hardware is touched.
"""

from __future__ import annotations

import numpy as np
import supervision as sv

from object_tracker.config import AimGains, COCO_BIRD_CLASS_ID
from object_tracker.turret_sink.actuator_sink import ActuatorSink
from object_tracker.turret_sink.aim_controller import AimCommand


class FakeTransport:
    def __init__(self):
        self.sent: list[AimCommand] = []
        self.closed = 0

    def send(self, command):
        self.sent.append(command)

    def close(self):
        self.closed += 1


def _tracked(tracker_ids, boxes):
    return sv.Detections(
        xyxy=np.asarray(boxes, dtype=float),
        class_id=np.asarray([COCO_BIRD_CLASS_ID] * len(boxes)),
        tracker_id=np.asarray(tracker_ids),
    )


def _gains():
    return AimGains(kp=0.1, deadzone_px=0.0, max_delta_deg=100.0)


FRAME_WH = (100, 50)  # centre = (50.0, 25.0)


def _blank_frame():
    return np.zeros((50, 100, 3), dtype=np.uint8)


def test_show_sends_no_command_when_no_tracks():
    transport = FakeTransport()
    sink = ActuatorSink(transport, _gains(), FRAME_WH)

    assert sink.show(_blank_frame(), None) is True
    assert transport.sent == []


def test_show_locks_and_sends_a_command_for_the_first_seen_id():
    transport = FakeTransport()
    sink = ActuatorSink(transport, _gains(), FRAME_WH)
    tracks = _tracked([5], [[60, 20, 80, 30]])  # centre (70, 25) -> error (20, 0)

    sink.show(_blank_frame(), tracks)

    assert len(transport.sent) == 1
    assert transport.sent[0].pan_delta > 0.0  # target right of centre -> pan right (+)


def test_show_keeps_the_lock_when_a_second_id_appears():
    transport = FakeTransport()
    sink = ActuatorSink(transport, _gains(), FRAME_WH)

    sink.show(_blank_frame(), _tracked([5], [[60, 20, 80, 30]]))  # locks 5 (right of centre)
    sink.show(
        _blank_frame(),
        _tracked([5, 9], [[60, 20, 80, 30], [0, 0, 10, 10]]),  # 9 is left of centre
    )

    # still locked on 5 (right of centre) -> pan stays positive, not the negative 9 would give
    assert transport.sent[-1].pan_delta > 0.0


def test_show_holds_position_and_relatches_after_losing_the_locked_id():
    transport = FakeTransport()
    sink = ActuatorSink(transport, _gains(), FRAME_WH)

    sink.show(_blank_frame(), _tracked([5], [[60, 20, 80, 30]]))  # locks 5, sends a command
    sent_after_first = len(transport.sent)

    sink.show(_blank_frame(), sv.Detections.empty())  # 5 is gone -> holds, no command
    assert len(transport.sent) == sent_after_first

    sink.show(_blank_frame(), _tracked([9], [[0, 0, 10, 10]]))  # re-latches onto 9
    assert len(transport.sent) == sent_after_first + 1
    assert transport.sent[-1].pan_delta < 0.0  # 9's centre (5,5) is left of frame centre (50,25)


def test_close_closes_the_transport():
    transport = FakeTransport()
    ActuatorSink(transport, _gains(), FRAME_WH).close()
    assert transport.closed == 1
