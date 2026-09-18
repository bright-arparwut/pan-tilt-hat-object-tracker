"""turret entrypoint (ADR-0013): wire the ServoDriver, the MJPEG streamer, and the UDP
command listener into one process.

The threading arrangement is a safety decision, not a performance one:

* The **listener owns the main thread** — it is the safety-critical plane, because it moves
  motors.
* The **streamer runs on a daemon thread** — if it dies, the turret still responds.
* SIGINT/SIGTERM **do not raise** into the listener. They set a stop ``Event`` that both
  planes poll cooperatively (the listener each ``recv_timeout``, the streamer each
  accept/frame), so each unwinds cleanly within one poll interval. An exception raised
  asynchronously into a loop that is mid-servo-write is exactly what you don't want.
* On exit the servos are recentered to a known safe pose — on **every** path.

Deploy under systemd with ``Restart=on-failure``.
"""

from __future__ import annotations

import argparse
import signal
import threading
from typing import Callable

from .listener import run_listener
from .servo import ServoDriver
from .streamer import run_streamer

DEFAULT_PORT = 9000
DEFAULT_STREAM_PORT = 8000
DEFAULT_CAMERA_INDEX = 0
DEFAULT_HOST = "0.0.0.0"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Flags: ``--port``, ``--stream-port``, ``--camera-index``, ``--csi``, ``--no-stream``,
    ``--host``, ``--allowed-source``.

    ``--no-stream`` matters more than it looks: it is how you bring up and test the command
    plane in week 10 before the camera works at all.
    """
    raise NotImplementedError("Week 10 — see learn/curriculum/week-10-wire-listener.md")


def _start_streamer_thread(
    args: argparse.Namespace, should_continue: Callable[[], bool]
) -> threading.Thread:
    """Start ``run_streamer`` on a daemon thread and return it."""
    raise NotImplementedError("Week 12 — see learn/curriculum/week-12-sentry-integration.md")


def run_turret(
    driver: ServoDriver,
    args: argparse.Namespace,
    stop: threading.Event,
    *,
    start_streamer: Callable[..., threading.Thread] = _start_streamer_thread,
    listener: Callable[..., None] = run_listener,
) -> int:
    """Start the streamer thread, then run the listener on this thread until ``stop`` is set;
    recenter the servos on the way out.

    ``start_streamer`` / ``listener`` are **injectable seams** so the whole wiring is testable
    with fakes and no hardware — which is the only reason this function has tests at all.

    Recenter in a ``finally``, and set ``stop`` there too so the streamer thread winds down
    even when the listener exits by an unexpected path.
    """
    raise NotImplementedError("Week 10 — see learn/curriculum/week-10-wire-listener.md")


def main(argv: list[str] | None = None) -> int:
    """Parse args, install the signal handlers, build the driver, run.

    Build the ``ServoDriver`` **first**, before advertising a stream: a HAT fault should fail
    immediately and loudly, not after the Mac has already connected.
    """
    raise NotImplementedError("Week 10 — see learn/curriculum/week-10-wire-listener.md")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
