from __future__ import annotations

import sys
import types
from unittest import mock

import pytest

from turret_pi.streamer import _CsiCamera, _encode_part, _open_camera, _open_csi_camera


def test_encode_part_frames_jpeg_as_a_multipart_chunk():
    part = _encode_part(b"JPEGDATA")
    assert part == (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n"
        b"Content-Length: 8\r\n\r\n"
        b"JPEGDATA\r\n"
    )


def test_open_camera_raises_a_clear_error_when_the_device_wont_open():
    fake_cap = mock.Mock()
    fake_cap.isOpened.return_value = False
    with mock.patch("turret_pi.streamer.cv2.VideoCapture", return_value=fake_cap):
        with pytest.raises(RuntimeError, match="could not open camera source: 7"):
            _open_camera(7)


def test_csi_camera_read_returns_ok_and_the_main_stream_array():
    picam2 = mock.Mock()
    picam2.capture_array.return_value = "FRAME"

    ok, frame = _CsiCamera(picam2).read()

    assert (ok, frame) == (True, "FRAME")
    picam2.capture_array.assert_called_once_with("main")


def test_csi_camera_release_stops_then_closes():
    picam2 = mock.Mock()

    _CsiCamera(picam2).release()

    picam2.stop.assert_called_once_with()
    picam2.close.assert_called_once_with()


def test_open_csi_camera_configures_video_and_starts(monkeypatch):
    picam2 = mock.Mock()
    picam2.create_video_configuration.return_value = "CONFIG"
    fake_module = types.SimpleNamespace(Picamera2=mock.Mock(return_value=picam2))
    monkeypatch.setitem(sys.modules, "picamera2", fake_module)

    cam = _open_csi_camera(1)

    fake_module.Picamera2.assert_called_once_with(1)
    picam2.create_video_configuration.assert_called_once_with(main={"format": "RGB888"})
    picam2.configure.assert_called_once_with("CONFIG")
    picam2.start.assert_called_once_with()
    assert isinstance(cam, _CsiCamera)


def test_open_csi_camera_raises_a_clear_error_when_picamera2_is_absent(monkeypatch):
    monkeypatch.setitem(sys.modules, "picamera2", None)  # force ImportError, even on a Pi

    with pytest.raises(RuntimeError, match="Picamera2 is not available"):
        _open_csi_camera(0)
