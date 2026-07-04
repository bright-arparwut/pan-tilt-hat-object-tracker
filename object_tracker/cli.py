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
    out = Path(output) if output else source.parent / f"{source.stem}.annotated.mp4"
    side = Path(sidecar) if sidecar else source.parent / f"{source.stem}.detections.jsonl"
    return RunPaths(source=source, output=out, sidecar=side)


def _resolve_classes(args) -> tuple[int, ...] | None:
    """Resolve which class ids to keep.

    General by default (ADR-0008): explicit ``--classes`` wins; otherwise keep **all**
    classes regardless of stock vs custom weights. Birds are no longer the default —
    pass ``--classes 14`` to reproduce bird-only on stock COCO weights.
    """
    if args.classes is not None:
        return tuple(args.classes)
    return None  # no --classes -> keep all classes


def _parse_turret_target(text: str) -> tuple[str, int]:
    """Parse ``--turret HOST[:PORT]`` (pure); PORT defaults to ``DEFAULT_TURRET_PORT`` when
    omitted. Raises ``ValueError`` on a malformed target (empty host, non-numeric port)."""
    host, sep, port_text = text.rpartition(":")
    if not sep:
        return text, DEFAULT_TURRET_PORT
    if not host or not port_text.isdigit():
        raise ValueError(f"--turret target must be HOST[:PORT], got {text!r}")
    return host, int(port_text)


def _maybe_add_turret(sink: FrameSink, args, frame_wh: tuple[int, int]) -> FrameSink:
    """Fold an Actuator Sink into ``sink`` when ``--turret`` is given, else return it as-is."""
    if args.turret is None:
        return sink
    host, port = _parse_turret_target(args.turret)
    turret = TurretConfig(
        host=host,
        port=port,
        gains=AimGains(
            kp=args.turret_kp,
            ki=args.turret_ki,
            kd=args.turret_kd,
            deadzone_px=args.turret_deadzone_px,
            max_delta_deg=args.turret_max_deg,
        ),
    )
    actuator = ActuatorSink(UdpAimTransport(turret.host, turret.port), turret.gains, frame_wh)
    return CompositeSink([sink, actuator])


def resolve_toggle(value: bool | None, is_live: bool) -> bool:
    """Resolve a tri-state CLI toggle (``--slice`` / ``--track`` / ``--zoom``; ADR-0010).

    An explicit flag always wins. When unset (``None``) the mode default applies: **on** for
    Offline, **off** for Live (the leanest live config), which is exactly ``not is_live``.
    """
    return value if value is not None else not is_live


def _build_file_io(args) -> tuple[FileSource, VideoFileSink, RunPaths]:
    """Build the Offline source + sink, raising a user-facing ``ValueError`` on bad input."""
    source_path = Path(args.source)
    if not source_path.exists():
        raise ValueError(f"source video not found: {source_path}")
    try:
        source = FileSource(source_path)
    except Exception as exc:  # noqa: BLE001 - surface any decode/open failure clearly
        raise ValueError(f"could not open video '{source_path}': {exc}") from exc
    paths = _derive_paths(source_path, args.output, args.sidecar)
    sink = VideoFileSink(paths.output, source.info)
    return source, sink, paths


def _select_source_sink(
    spec: CameraSpec | FileSpec, args
) -> tuple[FrameSource, FrameSink, Path | None, list[Path], str]:
    """Build the source + sink for the inferred mode (ADR-0010).

    Returns ``(source, sink, sidecar_path, written_paths, source_label)``. Live shows a window
    (with ``--sidecar`` / ``--record`` as opt-ins); Offline runs the file validation and writes
    the annotated video + sidecar. Raises ``ValueError`` / ``RuntimeError`` with a user-facing
    message on bad input — ``main`` prints it and exits non-zero.
    """
    written: list[Path] = []
    if isinstance(spec, CameraSpec):
        source = CameraSource(spec)  # raises RuntimeError if the device/URL won't open
        sink: FrameSink = WindowSink(f"object-tracker [{spec.target}] — q to quit")
        sidecar_path: Path | None = None
        if args.record is not None:
            record_path = Path(args.record)
            sink = CompositeSink([sink, VideoFileSink(record_path, source.info)])
            written.append(record_path)
        if args.sidecar is not None:
            sidecar_path = Path(args.sidecar)
            written.append(sidecar_path)
        return source, sink, sidecar_path, written, str(spec.target)

    file_source, file_sink, paths = _build_file_io(args)  # raises ValueError
    written.extend([paths.output, paths.sidecar])
    return file_source, file_sink, paths.sidecar, written, str(spec.path)


def validation_error(
    zoom_size: float,
    zoom_max: int,
    *,
    track: bool = True,
    track_buffer: int = DEFAULT_TRACK_BUFFER,
    zoom_track_id: int | None = None,
    turret: bool = False,
) -> str | None:
    """Return a user-facing message for an invalid arg combination, else ``None``."""
    if not 0.0 < zoom_size <= 1.0:
        return "--zoom-size must be in (0, 1]"
    if zoom_max < 1:
        return "--zoom-max must be >= 1"
    if track_buffer < 1:
        return "--track-buffer must be >= 1"
    if zoom_track_id is not None and not track:
        return "--zoom-track-id requires --track (it can't follow an id with --no-track)"
    if turret and not track:
        return "--turret requires --track"
    return None


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
    cfg = DetectConfig(
        weights=args.weights,
        conf=args.conf,
        classes=_resolve_classes(args),
        device=resolve_device(args.device),
        use_slicing=use_slicing,
        slice_wh=tuple(args.slice_wh),
        overlap_ratio_wh=tuple(args.overlap_ratio),
        overlap_filter=args.overlap_filter,
        thread_workers=args.thread_workers,
    )
    zoom = ZoomConfig(
        enabled=zoom_on,
        size=args.zoom_size,
        max_panels=args.zoom_max,
        track_id=args.zoom_track_id,
    )
    track = TrackConfig(
        enabled=track_on,
        tracker=TrackerKind[args.tracker.upper()],
        buffer=args.track_buffer,
    )
    return cfg, zoom, track


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    spec = classify_source(args.source)
    is_live = isinstance(spec, CameraSpec)

    if args.record is not None and not is_live:
        print("error: --record is Live-only (Offline writes the annotated video via --output)",
              file=sys.stderr)
        return 1

    if args.turret is not None and not is_live:
        print("error: --turret is Live-only (the turret aims a live camera feed)",
              file=sys.stderr)
        return 1

    # Resolve the mode-sensitive toggles before validating: an explicit flag wins, otherwise
    # Offline is on / Live is off (ADR-0010). Validation runs against the resolved values
    # (e.g. --zoom-track-id requires the *resolved* track).
    use_slicing = resolve_toggle(args.slice, is_live)
    track_on = resolve_toggle(args.track, is_live)
    zoom_on = resolve_toggle(args.zoom, is_live)

    err = validation_error(
        args.zoom_size,
        args.zoom_max,
        track=track_on,
        track_buffer=args.track_buffer,
        zoom_track_id=args.zoom_track_id,
        turret=args.turret is not None,
    )
    if err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    cfg, zoom, track = _build_configs(args, use_slicing, track_on, zoom_on)

    # Select source + sink from the inferred mode (Offline file validation runs inside; Live
    # skips it — the CameraSource open-failure is the live equivalent). One error arm prints
    # whatever user-facing message the builders raise.
    try:
        frame_source, sink, sidecar_path, written, source_label = _select_source_sink(spec, args)
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    # Only touch frame_source.info when --turret is given: it's the sole caller that needs
    # resolution_wh at this point, and several call sites (tests included) build a source
    # stand-in without a real .info until it's actually needed.
    if args.turret is not None:
        sink = _maybe_add_turret(sink, args, frame_source.info.resolution_wh)

    # Sliced inference can't host model.track() (ADR-0012), so --track wins over --slice.
    slicing_on = cfg.use_slicing and not track.enabled
    print(f"mode={'live' if is_live else 'offline'} source={source_label} "
          f"device={cfg.device} slicing={'on' if slicing_on else 'off'} "
          f"conf={cfg.conf} classes={cfg.classes if cfg.classes is not None else 'all'} "
          f"track={'on' if track.enabled else 'off'} "
          + (f"tracker={track.tracker.name.lower()} " if track.enabled else "")
          + f"zoom={'on' if zoom.enabled else 'off'} zoom_max={zoom.max_panels}"
          + (f" zoom_track_id={zoom.track_id}" if zoom.track_id is not None else "")
          + (f" turret={args.turret}" if args.turret is not None else ""))
    if track.enabled and cfg.use_slicing:
        print("note: --slice is ignored under --track (model.track() runs the model "
              "directly; sliced tracking is unsupported — ADR-0012)", file=sys.stderr)
    if slicing_on:
        # Guardrail: a degenerate --slice-wh (>= frame = no-op, or far smaller = slow +
        # fragmented boxes) can't be fixed by the slicer; warn before the loop commits to it.
        for msg in slice_warnings(
            cfg.slice_wh, cfg.overlap_ratio_wh, frame_source.info.resolution_wh
        ):
            print(f"warning: {msg}", file=sys.stderr)
    if is_live and not track.enabled:
        print("note: Live is noisy without --track (conf stays 0.15) — try --conf 0.3",
              file=sys.stderr)

    detector = build_detector(cfg, track)
    try:
        run(detector, frame_source, sink, zoom, track, sidecar_path=sidecar_path)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 0

    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
