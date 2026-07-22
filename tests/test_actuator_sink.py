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


def test_show_sends_a_command_carrying_plain_python_floats():
    """Regression (ADR-0013): track centres are numpy floats; if they flow into the AimCommand
    the turret wire's json.dumps raises 'float32 not JSON serializable' mid-run. The sent command
    must carry plain floats — and stay json-encodable end to end."""
    from object_tracker.turret_sink.wire import encode

    transport = FakeTransport()
    sink = ActuatorSink(transport, _gains(), FRAME_WH)

    sink.show(_blank_frame(), _tracked([5], [[60, 20, 80, 30]]))

    command = transport.sent[0]
    assert type(command.pan_delta) is float and type(command.tilt_delta) is float
    encode(command, seq=1)  # must not raise


def test_close_closes_the_transport():
    transport = FakeTransport()
    ActuatorSink(transport, _gains(), FRAME_WH).close()
    assert transport.closed == 1


class FakeClock:
    """Deterministic monotonic clock: advance() controls each frame's dt exactly."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, dt: float) -> None:
        self.now += dt


def _sentry_sink(transport):
    from object_tracker.config import SentryConfig

    clock = FakeClock()
    sink = ActuatorSink(
        transport, _gains(), FRAME_WH, sentry_config=SentryConfig(), clock=clock
    )
    return sink, clock


def _run_unlocked_frames(sink, clock, n, dt):
    for _ in range(n):
        clock.advance(dt)
        sink.show(_blank_frame(), sv.Detections.empty())


def test_unlocked_frames_within_grace_send_nothing():
    transport = FakeTransport()
    sink, clock = _sentry_sink(transport)

    # first frame's dt collapses to 0 (no prior timestamp) -> 1.0 s unlocked < 2.0 s grace
    _run_unlocked_frames(sink, clock, n=3, dt=0.5)

    assert transport.sent == []


def test_unlocked_past_grace_ships_sweeps_and_tilt_walks_to_default_then_zero():
    transport = FakeTransport()
    sink, clock = _sentry_sink(transport)

    # first frame's dt collapses to 0; 39 x 0.1 s = 3.9 s unlocked -> 19 sweep frames,
    # enough for the 22.5-deg tilt walk (15 frames at 1.5 deg/frame) plus settled frames
    _run_unlocked_frames(sink, clock, n=40, dt=0.1)

    assert transport.sent, "expected sweep commands after the grace period"
    assert all(c.pan_delta < 0.0 for c in transport.sent)  # first sweep is left
    # tilt: estimate starts at 67.5, default is 90 -> deltas walk up, then settle at 0
    assert transport.sent[0].tilt_delta > 0.0
    assert transport.sent[-1].tilt_delta == 0.0


def test_target_appearing_mid_sweep_ships_an_aim_command_on_the_next_frame():
    transport = FakeTransport()
    sink, clock = _sentry_sink(transport)
    _run_unlocked_frames(sink, clock, n=25, dt=0.1)  # sweeping
    sweeps = len(transport.sent)

    clock.advance(0.1)
    sink.show(_blank_frame(), _tracked([5], [[60, 20, 80, 30]]))  # target appears

    assert len(transport.sent) == sweeps + 1
    assert transport.sent[-1].pan_delta > 0.0  # aim toward the target (right of centre)


def test_aim_deltas_shipped_while_locked_shift_where_the_sweep_resumes():
    from object_tracker.config import SentryConfig

    transport = FakeTransport()
    sink, clock = _sentry_sink(transport)

    clock.advance(0.1)
    sink.show(_blank_frame(), _tracked([5], [[60, 20, 80, 30]]))  # locks id 5
    aim = transport.sent[-1]
    assert aim.pan_delta == 2.0  # kp=0.1 * error 20 px — the delta observe_aim folds in

    _run_unlocked_frames(sink, clock, n=25, dt=0.1)  # grace passes, sweep begins

    # Dead reckoning: the pan estimate was 90 + 2 = 92 when the sweep began (left);
    # the summed sweep deltas can never take the estimate below the pan clamp.
    swept = sum(c.pan_delta for c in transport.sent[1:])
    assert 92.0 + swept >= SentryConfig().pan_min_deg
