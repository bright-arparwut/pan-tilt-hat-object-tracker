"""turret entrypoint (ADR-0013): wire the ServoDriver, the MJPEG streamer, and the UDP
command listener into one process. The listener owns the **main thread** (safety-critical —
it moves motors); the streamer runs on a **daemon thread**. SIGINT/SIGTERM don't raise into
the listener — they set a stop ``Event`` that both planes poll cooperatively via
``should_continue`` (the listener each ``recv_timeout``, the streamer each accept/frame), so
each unwinds cleanly within one poll interval. Deploy under systemd (``Restart=on-failure``).
On exit the servos are recentered to a known safe pose.
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
    parser = argparse.ArgumentParser(
        prog="turret", description="Pan-tilt tracking turret (Raspberry Pi side)."
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="UDP Aim Command port")
    parser.add_argument("--stream-port", type=int, default=DEFAULT_STREAM_PORT,
                        help="HTTP MJPEG port")
    parser.add_argument("--camera-index", type=int, default=DEFAULT_CAMERA_INDEX,
                        help="camera index (OpenCV device or Picamera2 camera number)")
    parser.add_argument("--csi", action="store_true",
                        help="capture via Picamera2 (CSI camera module) instead of USB/OpenCV")
    parser.add_argument("--no-stream", action="store_true",
                        help="skip the MJPEG streamer (no Pi camera; e.g. Mac supplies frames)")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="listener bind host")
    parser.add_argument("--allowed-source", default=None,
                        help="only accept datagrams from this source IP (defense-in-depth)")
    return parser.parse_args(argv)


def _start_streamer_thread(
    args: argparse.Namespace, should_continue: Callable[[], bool]
) -> threading.Thread:
    thread = threading.Thread(
        target=run_streamer,
        kwargs={
            "camera_index": args.camera_index,
            "port": args.stream_port,
            "csi": args.csi,
            "should_continue": should_continue,
        },
        daemon=True,
    )
    thread.start()
    return thread


def run_turret(
    driver: ServoDriver,
    args: argparse.Namespace,
    stop: threading.Event,
    *,
    start_streamer: Callable[..., threading.Thread] = _start_streamer_thread,
    listener: Callable[..., None] = run_listener,
) -> int:
    """Start the streamer thread, then run the listener on this thread until ``stop`` is set;
    recenter the servos on the way out. ``start_streamer``/``listener`` are injectable seams
    so the wiring is testable with fakes and no hardware."""
    def should_continue() -> bool:
        return not stop.is_set()

    if not args.no_stream:
        start_streamer(args, should_continue)  # driver already built -> a servo fault failed fast
    try:
        listener(
            driver,
            args.port,
            host=args.host,
            allowed_source=args.allowed_source,
            should_continue=should_continue,
        )
    except KeyboardInterrupt:
        stop.set()
    finally:
        stop.set()          # tell the streamer thread to wind down too
        driver.recenter()   # leave the turret in a known safe pose
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    driver = ServoDriver()  # build first: a HAT fault fails before we advertise a stream
    return run_turret(driver, args, stop)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
