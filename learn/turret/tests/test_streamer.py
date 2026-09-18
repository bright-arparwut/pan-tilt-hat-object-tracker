"""Week 12 acceptance: the MJPEG part encoder (pure, Mac-testable)."""

from __future__ import annotations

from turret_pi.streamer import _encode_part


def test_encode_part_frames_a_jpeg_as_a_multipart_chunk():
    """A client that can't find the next boundary just hangs. The CRLFs are the whole job."""
    jpeg = b"\xff\xd8\xff\xe0FAKEJPEG\xff\xd9"
    part = _encode_part(jpeg)

    assert part.startswith(b"--frame\r\n")
    assert b"Content-Type: image/jpeg\r\n" in part
    assert f"Content-Length: {len(jpeg)}".encode() in part
    assert b"\r\n\r\n" + jpeg in part, "a blank line must separate headers from the body"
    assert part.endswith(b"\r\n")
