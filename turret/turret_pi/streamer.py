"""Frame streamer (ADR-0013 Phase 2): capture the Pi's camera and serve it as MJPEG over
HTTP so the Mac's existing ``CameraSource`` opens it as a plain stream URL — zero new Mac code.
Stdlib ``http.server`` + OpenCV only (KISS): the client is a ``cv2.VideoCapture``, not a
browser, so a minimal ``multipart/x-mixed-replace`` server suffices.

Two capture paths behind one ``Camera`` Protocol: a USB webcam via ``cv2.VideoCapture``
(the default), or a CSI camera module via Picamera2 (``csi=True``). Picamera2 is imported
lazily — like ``ServoDriver``'s hardware import — so this module imports and unit-tests on
the Mac with no Pi camera stack present.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Protocol

import cv2

_BOUNDARY = "frame"
_BIND_HOST = "0.0.0.0"  # serve on all interfaces so the Mac on the LAN can reach it
_POLL_TIMEOUT_S = 0.5   # how often the accept loop re-checks should_continue while idle


class Camera(Protocol):
    """What the stream loop needs from a capture device — ``cv2.VideoCapture``'s shape,
    so the USB path satisfies it natively and ``_CsiCamera`` adapts Picamera2 to it."""

    def read(self) -> tuple[bool, Any]: ...
    def release(self) -> None: ...


def _encode_part(jpeg: bytes) -> bytes:
    """Frame one JPEG as a ``multipart/x-mixed-replace`` part (pure; unit-tested on the Mac)."""
    return (
        b"--" + _BOUNDARY.encode() + b"\r\n"
        b"Content-Type: image/jpeg\r\n"
        b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
        + jpeg + b"\r\n"
    )


def _open_camera(camera_index: int) -> cv2.VideoCapture:
    """Open the capture device or raise a clear error (mirrors ``CameraSource``)."""
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"could not open camera source: {camera_index!r}")
    return cap


class _CsiCamera:
    """Adapt a started Picamera2 to the ``Camera`` Protocol."""

    def __init__(self, picam2: Any) -> None:
        self._picam2 = picam2

    def read(self) -> tuple[bool, Any]:
        return True, self._picam2.capture_array("main")

    def release(self) -> None:
        self._picam2.stop()
        self._picam2.close()


def _open_csi_camera(camera_index: int) -> _CsiCamera:
    """Open a CSI camera module via Picamera2, configured for the stream loop.

    libcamera's format names describe the little-endian word, not the byte order, so
    ``RGB888`` is B,G,R in memory — exactly what ``cv2.imencode`` expects, no cvtColor.
    """
    try:
        from picamera2 import Picamera2
    except ImportError as exc:
        raise RuntimeError(
            "Picamera2 is not available — on the Pi, install the OS camera stack "
            "(sudo apt install python3-picamera2) and expose it to the venv "
            "(see DEPLOY.md), or run without --csi for a USB camera"
        ) from exc
    picam2 = Picamera2(camera_index)
    picam2.configure(picam2.create_video_configuration(main={"format": "RGB888"}))
    picam2.start()
    return _CsiCamera(picam2)


def run_streamer(
    camera_index: int = 0,
    port: int = 8000,
    *,
    path: str = "/stream.mjpg",
    csi: bool = False,
    should_continue: Callable[[], bool] = lambda: True,
) -> None:
    """Blocking: capture ``camera_index`` (USB by default, CSI via Picamera2 when ``csi``),
    MJPEG-encode each frame, and serve ``multipart/x-mixed-replace; boundary=frame`` at
    ``http://<pi>:<port><path>``. Runs until ``should_continue()`` is False (main runs it
    on a daemon thread)."""
    cap: Camera = _open_csi_camera(camera_index) if csi else _open_camera(camera_index)

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            try:
                if self.path != path:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header(
                    "Content-Type", f"multipart/x-mixed-replace; boundary={_BOUNDARY}"
                )
                self.end_headers()
                while should_continue():
                    ok, frame = cap.read()
                    if not ok:
                        break
                    encoded, jpeg = cv2.imencode(".jpg", frame)
                    if not encoded:
                        continue
                    self.wfile.write(_encode_part(jpeg.tobytes()))
            except (BrokenPipeError, ConnectionResetError):
                return  # the client (the Mac) went away — end this response cleanly

        def log_message(self, *args) -> None:
            return  # quiet; the listener owns the console

    server = HTTPServer((_BIND_HOST, port), _Handler)
    server.timeout = _POLL_TIMEOUT_S
    try:
        while should_continue():
            server.handle_request()
    finally:
        server.server_close()
        cap.release()
