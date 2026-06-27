"""Unit tests for the CLI seam: argument parsing, validation, and class resolution.

Covers the pure CLI seams — no YOLO/video required:
- ``build_parser`` parsing of ``--zoom-max`` / ``--track*`` / ``--zoom-track-id``,
- ``validation_error`` for zoom and track arg combinations,
- ``_resolve_classes`` (general by default; ``--classes 14`` reproduces bird-only).
"""

from __future__ import annotations

import pytest

from object_tracker import cli
from object_tracker.cli import (
    _resolve_classes,
    build_parser,
    resolve_toggle,
    validation_error,
)
from object_tracker.config import (
    COCO_BIRD_CLASS_ID,
    DEFAULT_TRACK_BUFFER,
    DEFAULT_TRACKER,
    TrackerKind,
)


# --- CLI: zoom-max -----------------------------------------------------------------
def test_zoom_max_defaults_to_one():
    args = build_parser().parse_args(["--source", "x.mp4"])
    assert args.zoom_max == 1


def test_zoom_max_parses_explicit_value():
    args = build_parser().parse_args(["--source", "x.mp4", "--zoom-max", "6"])
    assert args.zoom_max == 6


# --- CLI: track flags (now tri-state: unset parses as None) ------------------------
def test_track_unset_parses_as_none():
    # Tri-state (ADR-0010): the parser no longer bakes in a default; main() resolves it.
    args = build_parser().parse_args(["--source", "x.mp4"])
    assert args.track is None


def test_track_flag_parses_true():
    args = build_parser().parse_args(["--source", "x.mp4", "--track"])
    assert args.track is True


def test_no_track_flag_disables_tracking():
    args = build_parser().parse_args(["--source", "x.mp4", "--no-track"])
    assert args.track is False


def test_slice_and_zoom_unset_parse_as_none():
    args = build_parser().parse_args(["--source", "x.mp4"])
    assert args.slice is None
    assert args.zoom is None


# --- tri-state resolution (resolve_toggle) -----------------------------------------
@pytest.mark.parametrize(
    "value,is_live,expected",
    [
        (None, False, True),   # Offline unset -> on
        (None, True, False),   # Live unset -> off (leanest)
        (True, True, True),    # explicit --flag wins in Live
        (False, False, False), # explicit --no-flag wins in Offline
        (True, False, True),
        (False, True, False),
    ],
)
def test_resolve_toggle(value, is_live, expected):
    assert resolve_toggle(value, is_live) is expected


def test_track_buffer_and_tracker_parse():
    args = build_parser().parse_args(
        ["--source", "x.mp4", "--track-buffer", "50", "--tracker", "ocsort"]
    )
    assert args.track_buffer == 50
    assert args.tracker == "ocsort"


def test_track_knob_defaults():
    args = build_parser().parse_args(["--source", "x.mp4"])
    assert args.track_buffer == DEFAULT_TRACK_BUFFER
    assert args.tracker == DEFAULT_TRACKER.name.lower()


def test_tracker_rejects_unknown_algorithm():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--source", "x.mp4", "--tracker", "sortmagic"])


def test_zoom_track_id_defaults_none_and_parses():
    assert build_parser().parse_args(["--source", "x.mp4"]).zoom_track_id is None
    args = build_parser().parse_args(["--source", "x.mp4", "--zoom-track-id", "7"])
    assert args.zoom_track_id == 7


# --- validation: zoom --------------------------------------------------------------
@pytest.mark.parametrize("zoom_max", [0, -1])
def test_validation_rejects_non_positive_zoom_max(zoom_max):
    err = validation_error(zoom_size=0.05, zoom_max=zoom_max)
    assert err is not None and "zoom-max" in err


def test_validation_accepts_valid_args():
    assert validation_error(zoom_size=0.05, zoom_max=1) is None


def test_validation_still_rejects_bad_zoom_size():
    assert validation_error(zoom_size=0.0, zoom_max=1) is not None


# --- validation: track -------------------------------------------------------------
def test_validation_accepts_valid_track_args():
    assert (
        validation_error(
            zoom_size=0.05,
            zoom_max=1,
            track=True,
            track_buffer=30,
            zoom_track_id=None,
        )
        is None
    )


@pytest.mark.parametrize("buffer", [0, -5])
def test_validation_rejects_non_positive_track_buffer(buffer):
    err = validation_error(zoom_size=0.05, zoom_max=1, track_buffer=buffer)
    assert err is not None and "track-buffer" in err


def test_validation_rejects_zoom_track_id_without_track():
    err = validation_error(zoom_size=0.05, zoom_max=1, track=False, zoom_track_id=7)
    assert err is not None and "zoom-track-id" in err


def test_validation_accepts_zoom_track_id_with_track():
    assert (
        validation_error(zoom_size=0.05, zoom_max=1, track=True, zoom_track_id=7)
        is None
    )


# --- class resolution (general by default; ADR-0008) -------------------------------
def test_resolve_classes_defaults_to_all_classes_on_stock_weights():
    # ADR-0008: no --classes -> all classes, independent of stock vs custom weights.
    args = build_parser().parse_args(["--source", "x.mp4"])
    assert _resolve_classes(args) is None


def test_resolve_classes_explicit_classes_detect_any_object():
    args = build_parser().parse_args(["--source", "x.mp4", "--classes", "0", "16"])
    assert _resolve_classes(args) == (0, 16)


def test_resolve_classes_classes_14_reproduces_bird_only():
    # The old bird default is now explicit: --classes 14 == bird-only.
    args = build_parser().parse_args(
        ["--source", "x.mp4", "--classes", str(COCO_BIRD_CLASS_ID)]
    )
    assert _resolve_classes(args) == (COCO_BIRD_CLASS_ID,)


# --- main(): mode inference + wiring (run/IO mocked; no YOLO/video/window) ----------
@pytest.fixture
def captured_run(monkeypatch):
    """Capture the args passed to ``cli.run`` and stub the detector build."""
    captured: dict = {}

    def fake_run(detector, source, sink, zoom, track, sidecar_path=None):
        captured.update(
            source=source, sink=sink, zoom=zoom, track=track, sidecar=sidecar_path
        )

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli, "build_detector", lambda cfg, track: object())
    return captured


def _stub_live(monkeypatch):
    source, sink = object(), object()
    monkeypatch.setattr(cli, "CameraSource", lambda spec: source)
    monkeypatch.setattr(cli, "WindowSink", lambda *a, **k: sink)
    monkeypatch.setattr(
        cli, "FileSource", lambda *a, **k: pytest.fail("FileSource used for a live source")
    )
    return source, sink


def test_main_source_0_selects_live_and_skips_file_checks(monkeypatch, captured_run):
    source, sink = _stub_live(monkeypatch)

    rc = cli.main(["--source", "0"])

    assert rc == 0
    assert captured_run["source"] is source
    assert captured_run["sink"] is sink
    assert captured_run["sidecar"] is None  # window-only by default
    assert captured_run["track"].enabled is False  # live defaults: off
    assert captured_run["zoom"].enabled is False


def test_main_stream_url_takes_the_live_path(monkeypatch, captured_run):
    source, _ = _stub_live(monkeypatch)
    rc = cli.main(["--source", "rtsp://cam/stream"])
    assert rc == 0
    assert captured_run["source"] is source


def test_main_live_explicit_track_overrides_off_default(monkeypatch, captured_run):
    _stub_live(monkeypatch)
    cli.main(["--source", "0", "--track"])
    assert captured_run["track"].enabled is True  # explicit flag wins in Live


def test_main_tracker_choice_threaded_into_track_config(monkeypatch, captured_run):
    _stub_live(monkeypatch)
    cli.main(["--source", "0", "--track", "--tracker", "botsort"])
    assert captured_run["track"].tracker is TrackerKind.BOTSORT


def test_main_live_open_failure_returns_1(monkeypatch, capsys):
    def boom(spec):
        raise RuntimeError("could not open live source: 0")

    monkeypatch.setattr(cli, "CameraSource", boom)
    monkeypatch.setattr(
        cli, "build_detector", lambda cfg, track: pytest.fail("built detector")
    )

    rc = cli.main(["--source", "0"])

    assert rc == 1
    assert "could not open" in capsys.readouterr().err


def test_main_live_zoom_track_id_without_track_rejected(monkeypatch, capsys):
    # In Live, --track resolves off, so --zoom-track-id must be rejected (resolved value).
    monkeypatch.setattr(cli, "CameraSource", lambda spec: pytest.fail("opened camera"))
    rc = cli.main(["--source", "0", "--zoom-track-id", "5"])
    assert rc == 1
    assert "zoom-track-id" in capsys.readouterr().err


def test_main_file_source_selects_offline(monkeypatch, captured_run, tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"pretend video")

    class FakeFileSource:
        def __init__(self, path):
            self.info = "INFO"

    monkeypatch.setattr(cli, "FileSource", FakeFileSource)
    monkeypatch.setattr(cli, "VideoFileSink", lambda out, info: ("file-sink", out))
    monkeypatch.setattr(
        cli, "CameraSource", lambda spec: pytest.fail("CameraSource used for a file source")
    )

    rc = cli.main(["--source", str(clip)])

    assert rc == 0
    assert isinstance(captured_run["source"], FakeFileSource)
    assert captured_run["track"].enabled is True  # offline defaults: on
    assert captured_run["zoom"].enabled is True
    assert captured_run["sidecar"] is not None  # offline always writes a sidecar


def test_main_missing_file_source_returns_1(capsys):
    rc = cli.main(["--source", "/no/such/clip.mp4"])
    assert rc == 1
    assert "not found" in capsys.readouterr().err


def test_main_offline_warns_on_tiny_slice_size(monkeypatch, captured_run, capsys, tmp_path):
    # --no-track turns slicing on (Offline) so the guardrail runs; a 100px tile on a 640x360
    # frame is degenerate and must warn before the (slow) loop commits to it.
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"pretend video")

    class _Info:
        resolution_wh = (640, 360)

    class FakeFileSource:
        def __init__(self, path):
            self.info = _Info()

    monkeypatch.setattr(cli, "FileSource", FakeFileSource)
    monkeypatch.setattr(cli, "VideoFileSink", lambda out, info: object())

    rc = cli.main(
        ["--source", str(clip), "--no-track", "--slice", "--slice-wh", "100", "100"]
    )

    assert rc == 0
    err = capsys.readouterr().err
    assert "warning:" in err and "tiles/frame" in err


# --- main(): opt-in Live outputs (--sidecar / --record) ----------------------------
class _SrcWithInfo:
    info = "INFO"


def test_main_live_sidecar_passes_path_to_run(monkeypatch, captured_run, tmp_path):
    _stub_live(monkeypatch)
    side = tmp_path / "s.jsonl"

    cli.main(["--source", "0", "--sidecar", str(side)])

    assert captured_run["sidecar"] == side  # opt-in sidecar path threaded through


def test_main_live_record_builds_composite_window_plus_file(monkeypatch, captured_run, tmp_path):
    window = object()
    monkeypatch.setattr(cli, "CameraSource", lambda spec: _SrcWithInfo())
    monkeypatch.setattr(cli, "WindowSink", lambda *a, **k: window)
    monkeypatch.setattr(cli, "VideoFileSink", lambda path, info: ("vfs", path, info))
    monkeypatch.setattr(cli, "CompositeSink", lambda sinks: ("composite", list(sinks)))

    rec = tmp_path / "rec.mp4"
    rc = cli.main(["--source", "0", "--record", str(rec)])

    assert rc == 0
    kind, children = captured_run["sink"]
    assert kind == "composite"
    assert children[0] is window  # window first (governs stop)
    assert children[1] == ("vfs", rec, "INFO")  # then the file recorder


def test_main_offline_record_is_rejected(capsys, tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"pretend video")

    rc = cli.main(["--source", str(clip), "--record", str(tmp_path / "rec.mp4")])

    assert rc == 1
    assert "Live-only" in capsys.readouterr().err
