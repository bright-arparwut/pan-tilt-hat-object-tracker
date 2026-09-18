"""Frame streamer (ADR-0013): capture the Pi's camera and serve it as MJPEG over HTTP, so
the Mac's existing ``CameraSource`` opens it as a plain stream URL — **zero new Mac code**.

That is the payoff of week 8's seam: because ``classify_source`` already treats an ``http://``
URL as a Live Source, the Pi only has to speak a format ``cv2.VideoCapture`` understands, and
the entire host side is unchanged.

Stdlib ``http.server`` + OpenCV only (KISS): the client is a ``cv2.VideoCapture``, not a
browser, so a minimal ``multipart/x-mixed-replace`` server suffices.

Two capture paths behind one ``Camera`` Protocol: a USB webcam via ``cv2.VideoCapture`` (the
default), or a CSI camera module via Picamera2 (``csi=True``). Picamera2 is imported **lazily**
— like ``ServoDriver``'s hardware import — so this module imports and unit-tests on the Mac
with no Pi camera stack present.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Protocol

import cv2

_BOUNDARY = "frame"
_BIND_HOST = "0.0.0.0"  # serve on all interfaces so the Mac on the LAN can reach it
_POLL_TIMEOUT_S = 0.5   # how often the accept loop re-checks should_continue while idle


class Camera(Protocol):
    """What the stream loop needs from a capture device.

    Deliberately ``cv2.VideoCapture``'s shape, so the USB path satisfies it **natively** with
    no adapter and only the CSI path needs one. Shaping a Protocol around the common case is
    a small decision that removes a whole class of wrapper code.
    """

    def read(self) -> tuple[bool, Any]: ...
    def release(self) -> None: ...


def _encode_part(jpeg: bytes) -> bytes:
    """Frame one JPEG as a ``multipart/x-mixed-replace`` part (pure; unit-tested on the Mac).

    The format is from 1995 and is three lines of headers: a ``--boundary`` marker, a
    ``Content-Type``, a ``Content-Length``, a blank line, the bytes, then ``\\r\\n``. Getting
    the CRLFs exactly right is the whole job — a client that can't find the next boundary
    just hangs.
    """
    raise NotImplementedError("Week 12 — see learn/curriculum/week-12-sentry-integration.md")


def _open_camera(camera_index: int) -> cv2.VideoCapture:
    """Open the USB capture device or raise a clear error (mirrors ``CameraSource``)."""
    raise NotImplementedError("Week 12 — see learn/curriculum/week-12-sentry-integration.md")


class _CsiCamera:
    """Adapt a started Picamera2 to the ``Camera`` Protocol."""

    def __init__(self, picam2: Any) -> None:
        raise NotImplementedError("Week 12 — see learn/curriculum/week-12-sentry-integration.md")

    def read(self) -> tuple[bool, Any]:
        raise NotImplementedError("Week 12 — see learn/curriculum/week-12-sentry-integration.md")

    def release(self) -> None:
        raise NotImplementedError("Week 12 — see learn/curriculum/week-12-sentry-integration.md")


def _open_csi_camera(camera_index: int) -> _CsiCamera:
    """Open a CSI camera module via Picamera2, configured for the stream loop.

    Import Picamera2 **inside** this function, and turn an ``ImportError`` into a message that
    tells the operator what to actually do (``apt install python3-picamera2``, recreate the
    venv with ``--system-site-packages``) — see ``DEPLOY.md``. A bare ImportError at 11pm on a
    Pi is worth about ten minutes of someone's life.

    One real gotcha: libcamera's format names describe the little-endian **word**, not the
    byte order — so ``RGB888`` is B,G,R in memory, which is exactly what ``cv2.imencode``
    wants. No ``cvtColor`` needed. Add one and you will invert your colours.
    """
    raise NotImplementedError("Week 12 — see learn/curriculum/week-12-sentry-integration.md")


def run_streamer(
    camera_index: int = 0,
    port: int = 8000,
    *,
    path: str = "/stream.mjpg",
    csi: bool = False,
    should_continue: Callable[[], bool] = lambda: True,
) -> None:
    """Blocking: capture, MJPEG-encode each frame, and serve
    ``multipart/x-mixed-replace; boundary=frame`` at ``http://<pi>:<port><path>``.

    Runs until ``should_continue()`` is False — ``main`` runs it on a daemon thread.

    The ``BaseHTTPRequestHandler`` scaffolding below is **given**; you supply the capture
    selection and the per-frame body. Two things to handle: a wrong path gets a 404, and a
    client that goes away (``BrokenPipeError`` / ``ConnectionResetError``) ends that response
    **cleanly** rather than killing the server — the Mac tracker restarts all the time.

    Set ``server.timeout`` and use ``handle_request()`` in a loop rather than
    ``serve_forever()``, so the loop can poll ``should_continue``.
    """
    raise NotImplementedError("Week 12 — see learn/curriculum/week-12-sentry-integration.md")
