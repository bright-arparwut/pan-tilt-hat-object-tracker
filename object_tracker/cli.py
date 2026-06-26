"""object-tracker CLI — general object detection + tracking over offline video.

A backend-agnostic detector (YOLO today) + optional sliced inference (the SAHI
*technique*, via ``supervision``'s ``InferenceSlicer``) runs over a video file, producing
an annotated video (boxes + a picture-in-picture zoom inset) and a per-frame JSONL
detections sidecar. Any class, any weights — birds are just one example (``--classes 14``).

The sidecar is the tracker-ready handoff; see the PRD at
``.scratch/object-tracker-refactor/PRD.md`` and the ADRs under ``docs/adr/``.

Run with:  ``uv run track --source clip.mp4 [--slice | --no-slice] ...``
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import supervision as sv

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
from .device import resolve_device
from .pipeline import run


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
    p.add_argument("--source", required=True, help="Input video file")
    p.add_argument("--weights", default=DEFAULT_WEIGHTS, help="YOLO weights (.pt)")
    p.add_argument("--device", default="auto", help="auto | cpu | mps | cuda | cuda:0")
    p.add_argument("--conf", type=float, default=DEFAULT_CONF, help="Confidence threshold")
    p.add_argument("--classes", type=int, nargs="+", default=None,
                   help="Class ids to keep (default: all classes; e.g. 14 for COCO bird)")
    p.add_argument("--slice", dest="slice", action=argparse.BooleanOptionalAction, default=True,
                   help="Toggle sliced inference (default: on)")
    p.add_argument("--slice-wh", type=int, nargs=2, default=list(DEFAULT_SLICE_WH),
                   metavar=("W", "H"), help="Slice size in px")
    p.add_argument("--overlap-ratio", type=float, nargs=2, default=list(DEFAULT_OVERLAP_RATIO),
                   metavar=("W", "H"), help="Slice overlap ratio")
    p.add_argument("--overlap-filter", choices=["nms", "nmm"], default="nms",
                   help="Slice merge strategy")
    p.add_argument("--thread-workers", type=int, default=DEFAULT_THREAD_WORKERS,
                   help="Parallel slice inference workers")
    p.add_argument("--zoom", action=argparse.BooleanOptionalAction, default=True,
                   help="Picture-in-picture zoom inset (default: on)")
    p.add_argument("--zoom-size", type=float, default=DEFAULT_ZOOM_SIZE,
                   help="Zoom crop side as fraction of frame width")
    p.add_argument("--zoom-max", type=int, default=1,
                   help="Follow up to N detections (top-N by confidence); default 1")
    p.add_argument("--track", action=argparse.BooleanOptionalAction, default=True,
                   help="In-loop sv.ByteTrack tracking (default: on)")
    p.add_argument("--track-buffer", type=int, default=DEFAULT_TRACK_BUFFER,
                   help="lost_track_buffer: frames a lost id (and its zoom slot) is held")
    p.add_argument("--track-activation", type=float, default=DEFAULT_TRACK_ACTIVATION,
                   help="track_activation_threshold: min conf to start a track")
    p.add_argument("--zoom-track-id", type=int, default=None,
                   help="Lock the zoom inset to one tracker_id (single-object; implies --track)")
    p.add_argument("--output", default=None, help="Annotated video path")
    p.add_argument("--sidecar", default=None, help="JSONL detections sidecar path")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    source = Path(args.source)
    if not source.exists():
        print(f"error: source video not found: {source}", file=sys.stderr)
        return 1
    try:
        sv.VideoInfo.from_video_path(str(source))
    except Exception as exc:  # noqa: BLE001 - surface any decode/open failure clearly
        print(f"error: could not open video '{source}': {exc}", file=sys.stderr)
        return 1
    err = validation_error(
        args.zoom_size,
        args.zoom_max,
        track=args.track,
        track_buffer=args.track_buffer,
        track_activation=args.track_activation,
        zoom_track_id=args.zoom_track_id,
    )
    if err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    cfg = DetectConfig(
        weights=args.weights,
        conf=args.conf,
        classes=_resolve_classes(args),
        device=resolve_device(args.device),
        use_slicing=args.slice,
        slice_wh=tuple(args.slice_wh),
        overlap_ratio_wh=tuple(args.overlap_ratio),
        overlap_filter=args.overlap_filter,
        thread_workers=args.thread_workers,
    )
    paths = _derive_paths(source, args.output, args.sidecar)

    zoom = ZoomConfig(
        enabled=args.zoom,
        size=args.zoom_size,
        max_panels=args.zoom_max,
        track_id=args.zoom_track_id,
    )
    track = TrackConfig(
        enabled=args.track, activation=args.track_activation, buffer=args.track_buffer
    )
    print(f"device={cfg.device} slicing={'on' if cfg.use_slicing else 'off'} "
          f"conf={cfg.conf} classes={cfg.classes if cfg.classes is not None else 'all'} "
          f"track={'on' if track.enabled else 'off'} "
          f"zoom={'on' if zoom.enabled else 'off'} zoom_max={zoom.max_panels}"
          + (f" zoom_track_id={zoom.track_id}" if zoom.track_id is not None else ""))
    run(cfg, paths, zoom, track)
    print(f"wrote {paths.output}\nwrote {paths.sidecar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
