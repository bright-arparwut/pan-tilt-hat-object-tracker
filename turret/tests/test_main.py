from __future__ import annotations

import threading

from turret_pi.main import _parse_args, run_turret


def test_parse_args_defaults():
    args = _parse_args([])
    assert args.port == 9000
    assert args.stream_port == 8000
    assert args.camera_index == 0
    assert args.host == "0.0.0.0"
    assert args.allowed_source is None


def test_parse_args_overrides():
    args = _parse_args(
        ["--port", "9100", "--stream-port", "8100", "--camera-index", "2",
         "--host", "127.0.0.1", "--allowed-source", "10.0.0.5"]
    )
    assert (args.port, args.stream_port, args.camera_index) == (9100, 8100, 2)
    assert args.host == "127.0.0.1"
    assert args.allowed_source == "10.0.0.5"


class _FakeDriver:
    """A ServoDriver stand-in: records recenter() calls; no HAT."""

    def __init__(self) -> None:
        self.recentered = 0

    def recenter(self) -> None:
        self.recentered += 1


def test_run_turret_starts_streamer_before_listener_then_recenters_on_exit():
    driver = _FakeDriver()
    calls: list = []

    def fake_start_streamer(args, should_continue):
        calls.append("streamer")
        return threading.Thread(target=lambda: None)  # never started; wiring test only

    def fake_listener(servo, port, *, host, allowed_source, should_continue):
        calls.append(("listener", servo, port, host, allowed_source))
        # returns immediately, as if should_continue() had already gone False

    args = _parse_args(["--port", "9000", "--host", "127.0.0.1"])
    stop = threading.Event()

    rc = run_turret(
        driver, args, stop,
        start_streamer=fake_start_streamer,
        listener=fake_listener,
    )

    assert rc == 0
    assert calls[0] == "streamer"                       # streamer first (startup order)
    assert calls[1][0] == "listener"                    # then the listener
    assert calls[1][1] is driver and calls[1][2] == 9000  # driver + port wired through
    assert calls[1][3] == "127.0.0.1"                   # host forwarded
    assert driver.recentered == 1                       # recentered on the way out
    assert stop.is_set()                                # streamer told to wind down
