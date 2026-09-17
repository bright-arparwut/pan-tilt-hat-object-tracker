"""Week 12 acceptance: process wiring, via injected seams (no hardware, no threads spawned)."""

from __future__ import annotations

import argparse
import threading

from turret_pi.main import run_turret


class _FakeDriver:
    def __init__(self):
        self.recentered = False

    def recenter(self):
        self.recentered = True


def _args(**overrides):
    base = dict(port=9000, stream_port=8000, camera_index=0, csi=False,
                no_stream=False, host="0.0.0.0", allowed_source=None)
    base.update(overrides)
    return argparse.Namespace(**base)


def test_the_servos_are_recentered_even_when_the_listener_raises():
    """Leave the turret in a known safe pose on every exit path, including a crash."""
    driver = _FakeDriver()
    started = []

    def _boom(*a, **kw):
        raise RuntimeError("listener died")

    try:
        run_turret(
            driver, _args(no_stream=True), threading.Event(),
            start_streamer=lambda *a, **kw: started.append(True),
            listener=_boom,
        )
    except RuntimeError:
        pass
    assert driver.recentered


def test_no_stream_skips_the_streamer_thread():
    driver = _FakeDriver()
    started = []
    run_turret(
        driver, _args(no_stream=True), threading.Event(),
        start_streamer=lambda *a, **kw: started.append(True),
        listener=lambda *a, **kw: None,
    )
    assert started == [], "--no-stream is how you bring up the command plane alone"
    assert driver.recentered
