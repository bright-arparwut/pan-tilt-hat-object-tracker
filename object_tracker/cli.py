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
    DEFAULT_CONF,
    DEFAULT_OVERLAP_RATIO,
    DEFAULT_SLICE_WH,
    DEFAULT_THREAD_WORKERS,
    DEFAULT_TRACK_ACTIVATION,
    DEFAULT_TRACK_BUFFER,
    DEFAULT_WEIGHTS,
    DEFAULT_ZOOM_SIZE,
    DetectConfig,
    RunPaths,
    TrackConfig,
    ZoomConfig,
)
from .detection import build_detector
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
    track_activation: float = DEFAULT_TRACK_ACTIVATION,
    zoom_track_id: int | None = None,
) -> str | None:
    """Return a user-facing message for an invalid arg combination, else ``None``."""
    if not 0.0 < zoom_size <= 1.0:
        return "--zoom-size must be in (0, 1]"
    if zoom_max < 1:
        return "--zoom-max must be >= 1"
    if track_buffer < 1:
        return "--track-buffer must be >= 1"
    if not 0.0 < track_activation <= 1.0:
        return "--track-activation must be in (0, 1]"
    if zoom_track_id is not None and not track:
        return "--zoom-track-id requires --track (it can't follow an id with --no-track)"
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
                   help="In-loop sv.ByteTrack tracking (default: on Offline, off Live)")
    p.add_argument("--track-buffer", type=int, default=DEFAULT_TRACK_BUFFER,
                   help="lost_track_buffer: frames a lost id (and its zoom slot) is held")
    p.add_argument("--track-activation", type=float, default=DEFAULT_TRACK_ACTIVATION,
                   help="track_activation_threshold: min conf to start a track")
    p.add_argument("--zoom-track-id", type=int, default=None,
                   help="Lock the zoom inset to one tracker_id (single-object; requires --track, "
                        "which is off by default in Live)")
    p.add_argument("--output", default=None, help="Annotated video path (Offline)")
    p.add_argument("--sidecar", default=None,
                   help="JSONL detections sidecar path (Offline default-derived; Live opt-in, "
                        "rows carry a capture ts)")
    p.add_argument("--record", default=None,
                   help="Live only: also write an annotated .mp4 alongside the preview window")
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
        enabled=track_on, activation=args.track_activation, buffer=args.track_buffer
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
        track_activation=args.track_activation,
        zoom_track_id=args.zoom_track_id,
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

    print(f"mode={'live' if is_live else 'offline'} source={source_label} "
          f"device={cfg.device} slicing={'on' if cfg.use_slicing else 'off'} "
          f"conf={cfg.conf} classes={cfg.classes if cfg.classes is not None else 'all'} "
          f"track={'on' if track.enabled else 'off'} "
          f"zoom={'on' if zoom.enabled else 'off'} zoom_max={zoom.max_panels}"
          + (f" zoom_track_id={zoom.track_id}" if zoom.track_id is not None else ""))
    if is_live and not track.enabled:
        print("note: Live is noisy without --track (conf stays 0.15) — try --conf 0.3",
              file=sys.stderr)

    detector = build_detector(cfg)
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
