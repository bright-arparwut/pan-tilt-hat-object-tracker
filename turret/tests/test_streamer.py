from __future__ import annotations

from unittest import mock

import pytest

from turret_pi.streamer import _encode_part, _open_camera


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
