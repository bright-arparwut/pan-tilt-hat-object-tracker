"""object-tracker CLI — general object detection + tracking, Offline or Live.

A backend-agnostic detector (YOLO today) + optional sliced inference (the SAHI
*technique*, via ``supervision``'s ``InferenceSlicer``) runs over a video, producing an
annotated video (boxes + a picture-in-picture zoom inset) and a per-frame JSONL detections
sidecar. Any class, any weights — birds are just one example (``--classes 14``).

The **mode is inferred from ``--source``** (ADR-0010): a file path is **Offline**; a camera
index (``--source 0``) or stream URL (``--source rtsp://…``) is **Live** — frames stream into
an on-screen preview window (press ``q`` to quit). Live defaults are leanest (slicing / track
/ zoom off, window-only); Offline defaults are unchanged.

The sidecar is the tracker-ready handoff; see the PRD at
``.scratch/object-tracker-refactor/PRD.md`` and the ADRs under ``docs/adr/``.

Run with:  ``uv run track --source clip.mp4 ...``  or  ``uv run track --source 0 ...``
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import (
    AimGains,
    DEFAULT_CONF,
    DEFAULT_OVERLAP_RATIO,
    DEFAULT_SLICE_WH,
    DEFAULT_THREAD_WORKERS,
    DEFAULT_TRACK_BUFFER,
    DEFAULT_TRACKER,
    DEFAULT_TURRET_DEADZONE_PX,
    DEFAULT_TURRET_KD,
    DEFAULT_TURRET_KI,
    DEFAULT_TURRET_KP,
    DEFAULT_TURRET_MAX_DELTA_DEG,
    DEFAULT_TURRET_PORT,
    DEFAULT_WEIGHTS,
    DEFAULT_ZOOM_SIZE,
    DetectConfig,
    RunPaths,
    TrackConfig,
    TrackerKind,
    TurretConfig,
    ZoomConfig,
)
from .detection import build_detector, slice_warnings
from .device import resolve_device
from .pipeline import run
from .sinks import CompositeSink, FrameSink, VideoFileSink, WindowSink
from .sources import (
    CameraSource,
    CameraSpec,
    FileSource,
    FileSpec,
    FrameSource,
    classify_source,
)
from .turret_sink import ActuatorSink, UdpAimTransport


def _derive_paths(source: Path, output: str | None, sidecar: str | None) -> RunPaths:
    """Default the output paths from the source stem: ``<source>.annotated.mp4`` and
    ``<source>.detections.jsonl``, unless explicitly overridden."""
    raise NotImplementedError("Week 3 — see learn/curriculum/week-03-annotation-sidecar.md")


def _resolve_classes(args) -> tuple[int, ...] | None:
    """Resolve which class ids to keep.

    General by default (ADR-0008): explicit ``--classes`` wins; otherwise keep **all**
    classes, stock weights or custom. ``None`` means "keep everything", not "keep nothing".
    """
    raise NotImplementedError("Week 2 — see learn/curriculum/week-02-detection.md")


def _parse_turret_target(text: str) -> tuple[str, int]:
    """Parse ``--turret HOST[:PORT]`` (pure); PORT defaults to ``DEFAULT_TURRET_PORT``.

    Raise ``ValueError`` on a malformed target (empty host, non-numeric port). Note the
    parsing hazard: hosts can contain colons too. Think about ``rpartition``.
    """
    raise NotImplementedError("Week 11 — see learn/curriculum/week-11-visual-servoing.md")


def _maybe_add_turret(sink: FrameSink, args, frame_wh: tuple[int, int]) -> FrameSink:
    """Fold an Actuator Sink into ``sink`` when ``--turret`` is given, else return it as-is.

    The turret is just another sink composed onto the stack — the pipeline never learns that
    one of its sinks drives a motor. That is week 8's seam paying off.
    """
    raise NotImplementedError("Week 11 — see learn/curriculum/week-11-visual-servoing.md")


def resolve_toggle(value: bool | None, is_live: bool) -> bool:
    """Resolve a tri-state CLI toggle (``--slice`` / ``--track`` / ``--zoom``; ADR-0010).

    An explicit flag always wins. When unset (``None``) the **mode default** applies: on for
    Offline, off for Live (the leanest live config). Four lines, one real product decision.
    """
    raise NotImplementedError("Week 8 — see learn/curriculum/week-08-live-mode.md")


def _build_file_io(args) -> tuple[FileSource, VideoFileSink, RunPaths]:
    """Build the Offline source + sink, raising a user-facing ``ValueError`` on bad input.

    Validate the source path exists *before* opening it, and wrap any decode/open failure in
    a message that names the file. A raw OpenCV failure tells the user nothing.
    """
    raise NotImplementedError("Week 3 — see learn/curriculum/week-03-annotation-sidecar.md")


def _select_source_sink(
    spec: CameraSpec | FileSpec, args
) -> tuple[FrameSource, FrameSink, Path | None, list[Path], str]:
    """Build the source + sink for the inferred mode (ADR-0010).

    Returns ``(source, sink, sidecar_path, written_paths, source_label)``.

    Live shows a window, with ``--sidecar`` / ``--record`` as **opt-ins** — a live run writes
    nothing to disk unless asked. Offline runs the file validation and always writes the
    annotated video + sidecar.

    Raise ``ValueError`` / ``RuntimeError`` with a user-facing message on bad input; ``main``
    prints it and exits non-zero. One error arm, many failure causes.
    """
    raise NotImplementedError("Week 8 — see learn/curriculum/week-08-live-mode.md")


def validation_error(
    zoom_size: float,
    zoom_max: int,
    *,
    track: bool = True,
    track_buffer: int = DEFAULT_TRACK_BUFFER,
    zoom_track_id: int | None = None,
    turret: bool = False,
) -> str | None:
    """Return a user-facing message for an invalid arg combination, else ``None``.

    Pure and keyword-only, so it is exhaustively testable without building a parser. Note it
    must run against the **resolved** toggles, not the raw flags — ``--zoom-track-id``
    requires tracking to be *actually* on, and in Live mode tracking is off by default.
    """
    raise NotImplementedError("Week 8 — see learn/curriculum/week-08-live-mode.md")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="track", description=__doc__)
    p.add_argument("--source", required=True,
                   help="Video file (Offline), camera index e.g. 0, or stream URL (Live)")
    p.add_argument("--weights", default=DEFAULT_WEIGHTS, help="YOLO weights (.pt)")
    p.add_argument("--device", default="auto", help="auto | cpu | mps | cuda | cuda:0")
    p.add_argument("--conf", type=float, default=DEFAULT_CONF,
                   help="Confidence threshold (0.15; Live is noisy without --track — try --conf 0.3)")
    p.add_argument("--classes", type=int, nargs="+", default=None,
                   help="Class ids to keep (default: all classes; e.g. 14 for COCO bird)")
    p.add_argument("--slice", dest="slice", action=argparse.BooleanOptionalAction, default=None,
                   help="Toggle sliced inference (default: on Offline, off Live)")
    p.add_argument("--slice-wh", type=int, nargs=2, default=list(DEFAULT_SLICE_WH),
                   metavar=("W", "H"), help="Slice size in px")
    p.add_argument("--overlap-ratio", type=float, nargs=2, default=list(DEFAULT_OVERLAP_RATIO),
                   metavar=("W", "H"), help="Slice overlap ratio")
    p.add_argument("--overlap-filter", choices=["nms", "nmm"], default="nms",
                   help="Slice merge strategy")
    p.add_argument("--thread-workers", type=int, default=DEFAULT_THREAD_WORKERS,
                   help="Parallel slice inference workers")
    p.add_argument("--zoom", action=argparse.BooleanOptionalAction, default=None,
                   help="Picture-in-picture zoom inset (default: on Offline, off Live)")
    p.add_argument("--zoom-size", type=float, default=DEFAULT_ZOOM_SIZE,
                   help="Zoom crop side as fraction of frame width")
    p.add_argument("--zoom-max", type=int, default=1,
                   help="Follow up to N detections (top-N by confidence); default 1")
    p.add_argument("--track", action=argparse.BooleanOptionalAction, default=None,
                   help="Multi-object tracking via Ultralytics model.track() "
                        "(default: on Offline, off Live)")
    p.add_argument("--tracker", choices=[k.name.lower() for k in TrackerKind],
                   default=DEFAULT_TRACKER.name.lower(),
                   help="Tracking algorithm when --track (default: bytetrack); thresholds "
                        "live in the tracker's shipped yaml")
    p.add_argument("--track-buffer", type=int, default=DEFAULT_TRACK_BUFFER,
                   help="Frames a lost id's zoom slot is held (mirrors the tracker's "
                        "track_buffer)")
    p.add_argument("--zoom-track-id", type=int, default=None,
                   help="Lock the zoom inset to one tracker_id (single-object; requires --track, "
                        "which is off by default in Live)")
    p.add_argument("--output", default=None, help="Annotated video path (Offline)")
    p.add_argument("--sidecar", default=None,
                   help="JSONL detections sidecar path (Offline default-derived; Live opt-in, "
                        "rows carry a capture ts)")
    p.add_argument("--record", default=None,
                   help="Live only: also write an annotated .mp4 alongside the preview window")
    p.add_argument("--turret", default=None, metavar="HOST[:PORT]",
                   help="Live only, requires --track: also aim a pan-tilt turret via UDP "
                        f"Aim Commands (default port {DEFAULT_TURRET_PORT}; ADR-0013)")
    p.add_argument("--turret-kp", type=float, default=DEFAULT_TURRET_KP,
                   help="Aim Controller proportional gain (deg per px error)")
    p.add_argument("--turret-ki", type=float, default=DEFAULT_TURRET_KI,
                   help="Aim Controller integral gain (0.0 = P-only, Phase 3)")
    p.add_argument("--turret-kd", type=float, default=DEFAULT_TURRET_KD,
                   help="Aim Controller derivative gain (0.0 = P-only, Phase 3)")
    p.add_argument("--turret-deadzone-px", type=float, default=DEFAULT_TURRET_DEADZONE_PX,
                   help="Pixel error below this is treated as zero (jitter floor)")
    p.add_argument("--turret-max-deg", type=float, default=DEFAULT_TURRET_MAX_DELTA_DEG,
                   help="Per-step slew clamp on a single Aim Command (deg)")
    return p


def _build_configs(
    args, use_slicing: bool, track_on: bool, zoom_on: bool
) -> tuple[DetectConfig, ZoomConfig, TrackConfig]:
    """Assemble the three frozen run-configs from parsed args + the resolved toggles."""
    raise NotImplementedError("Week 3 — see learn/curriculum/week-03-annotation-sidecar.md")


def main(argv: list[str] | None = None) -> int:
    """Parse, validate, wire, run. Returns a process exit code.

    The order matters, and it is the order the ADRs force:

      1. ``classify_source`` → the mode (never a ``--live`` flag; ADR-0010).
      2. Reject mode-only flags (``--record`` and ``--turret`` are Live-only).
      3. ``resolve_toggle`` the tri-state flags, so validation sees resolved values.
      4. ``validation_error`` → print and exit 1 on a bad combination.
      5. Build the configs, then the source/sink (one error arm for both builders).
      6. Print the run banner and any guardrail warnings (degenerate ``--slice-wh``,
         ``--slice`` ignored under ``--track``, Live-without-track noise).
      7. Build the detector, run the loop, catch ``KeyboardInterrupt`` as a clean exit 0.
      8. Report what was written.

    Touch ``frame_source.info`` only where you actually need it — several call sites build a
    source stand-in without a real ``.info`` until it is required.
    """
    raise NotImplementedError("Week 3 — see learn/curriculum/week-03-annotation-sidecar.md")


if __name__ == "__main__":
    raise SystemExit(main())
