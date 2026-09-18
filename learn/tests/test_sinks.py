"""Week 8 acceptance: sink composition and teardown."""

from __future__ import annotations

import numpy as np
import pytest

from object_tracker.sinks import CompositeSink


class _RecordingSink:
    def __init__(self, keep_going=True, close_error=None):
        self.frames = 0
        self.closed = False
        self._keep_going = keep_going
        self._close_error = close_error

    def show(self, frame, tracks=None):
        self.frames += 1
        return self._keep_going

    def close(self):
        self.closed = True
        if self._close_error:
            raise self._close_error


def test_composite_calls_every_sink_even_when_one_says_stop():
    """No short-circuit: a recorder must still capture the frame the window quit on."""
    stopper = _RecordingSink(keep_going=False)
    recorder = _RecordingSink(keep_going=True)
    composite = CompositeSink([stopper, recorder])

    assert composite.show(np.zeros((4, 4, 3), dtype=np.uint8)) is False
    assert recorder.frames == 1, "the second sink must still have received the frame"


def test_composite_close_reraises_the_first_failure_after_closing_all():
    boom = RuntimeError("first failure")
    failing = _RecordingSink(close_error=boom)
    other = _RecordingSink()
    composite = CompositeSink([failing, other])

    with pytest.raises(RuntimeError, match="first failure"):
        composite.close()
    assert other.closed, "every child must be closed even though an earlier close raised"
