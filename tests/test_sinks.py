"""Tests for the Live Preview sinks (ADR-0010) — every cv2 call is monkeypatched.

``WindowSink`` reports stop on ``q`` / window-close; ``CompositeSink`` fans one frame out to
several sinks (the ``--record`` window+file case), ANDs their stop signals, and closes every
child even if one raises. No real window is ever opened.
"""

from __future__ import annotations

import numpy as np
import pytest
import supervision as sv

from object_tracker import sinks
from object_tracker.sinks import CompositeSink, WindowSink


def _frame() -> np.ndarray:
    return np.zeros((48, 64, 3), dtype=np.uint8)


def _patch_window(monkeypatch, *, key=-1, visible=1.0):
    monkeypatch.setattr(sinks.cv2, "imshow", lambda name, frame: None)
    monkeypatch.setattr(sinks.cv2, "waitKey", lambda delay: key)
    monkeypatch.setattr(sinks.cv2, "getWindowProperty", lambda name, prop: visible)


# --- WindowSink --------------------------------------------------------------------


def test_window_sink_continues_when_idle(monkeypatch):
    _patch_window(monkeypatch, key=-1, visible=1.0)
    assert WindowSink().show(_frame()) is True


def test_window_sink_stops_on_q(monkeypatch):
    _patch_window(monkeypatch, key=ord("q"), visible=1.0)
    assert WindowSink().show(_frame()) is False


def test_window_sink_stops_on_window_close(monkeypatch):
    _patch_window(monkeypatch, key=-1, visible=0.0)  # WND_PROP_VISIBLE < 1
    assert WindowSink().show(_frame()) is False


def test_window_sink_close_destroys_named_window(monkeypatch):
    destroyed: list[str] = []
    monkeypatch.setattr(sinks.cv2, "destroyWindow", lambda name: destroyed.append(name))
    WindowSink("my-window").close()
    assert destroyed == ["my-window"]


def test_window_sink_show_accepts_a_tracks_argument(monkeypatch):
    _patch_window(monkeypatch, key=-1, visible=1.0)
    assert WindowSink().show(_frame(), sv.Detections.empty()) is True


# --- CompositeSink -----------------------------------------------------------------


class FakeSink:
    def __init__(self, *, show_result=True, raise_on_close=False):
        self.shown: list[np.ndarray] = []
        self.tracks_received: list = []
        self.closed = 0
        self._show_result = show_result
        self._raise_on_close = raise_on_close

    def show(self, frame: np.ndarray, tracks=None) -> bool:
        self.shown.append(frame)
        self.tracks_received.append(tracks)
        return self._show_result

    def close(self) -> None:
        self.closed += 1
        if self._raise_on_close:
            raise RuntimeError("close failed")


def test_composite_calls_every_child_and_ands_results():
    keep_on, stop = FakeSink(show_result=True), FakeSink(show_result=False)
    composite = CompositeSink([keep_on, stop])

    result = composite.show(_frame())

    assert result is False  # AND: one child asked to stop
    assert len(keep_on.shown) == 1 and len(stop.shown) == 1  # both shown, no short-circuit


def test_composite_show_true_only_when_all_true():
    a, b = FakeSink(show_result=True), FakeSink(show_result=True)
    assert CompositeSink([a, b]).show(_frame()) is True


def test_composite_close_closes_all_children_even_if_one_raises():
    raising, ok = FakeSink(raise_on_close=True), FakeSink()
    composite = CompositeSink([raising, ok])

    with pytest.raises(RuntimeError):
        composite.close()

    assert raising.closed == 1 and ok.closed == 1  # both closed despite the failure


def test_composite_forwards_tracks_to_every_child():
    a, b = FakeSink(), FakeSink()
    composite = CompositeSink([a, b])
    tracks = sv.Detections.empty()

    composite.show(_frame(), tracks)

    assert a.tracks_received == [tracks]
    assert b.tracks_received == [tracks]
