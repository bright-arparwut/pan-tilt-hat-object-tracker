"""In-loop ByteTrack tracking + the per-run track runtime (ADR-0006)."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Protocol, cast

import numpy as np
import supervision as sv

from .annotators import (
    DetectionAnn,
    build_detection_annotator,
    build_label_annotator,
    build_trace_annotator,
)
from .config import TrackConfig, ZoomConfig
from .zoom import ZoomSlots


class _ByteTracker(Protocol):
    """The slice of ``sv.ByteTrack`` the loop depends on.

    ``sv.ByteTrack`` is a deprecation proxy (removed in supervision 0.30) that type
    checkers can't treat as a class, so we type against this structural interface instead.
    Runtime still constructs ``sv.ByteTrack`` per ADR-0006.
    """

    def update_with_detections(self, detections: sv.Detections) -> sv.Detections: ...


@dataclass(frozen=True)
class _TrackAnnotators:
    """Confirmed-track video annotators (coloured by ``tracker_id``)."""

    mark: DetectionAnn  # the DETECTION_STYLE annotator (ADR-0011); coloured by tracker_id
    label: sv.LabelAnnotator
    trace: sv.TraceAnnotator


def _build_track_annotators(frame_wh: tuple[int, int]) -> _TrackAnnotators:
    """Compose the themed factory builders into the track bundle (coloured by tracker_id)."""
    track = sv.ColorLookup.TRACK
    return _TrackAnnotators(
        mark=build_detection_annotator(frame_wh, track),
        label=build_label_annotator(frame_wh, track),
        trace=build_trace_annotator(frame_wh, track),
    )


def _build_track_map(confirmed: sv.Detections) -> dict[int, int]:
    """Exact ``raw_row -> track_id`` map via the ``_idx`` stashed before tracking."""
    if confirmed.tracker_id is None or "_idx" not in confirmed.data:
        return {}
    return {
        int(raw_idx): int(tid)
        for raw_idx, tid in zip(confirmed.data["_idx"], confirmed.tracker_id)
    }


def _present_centers(confirmed: sv.Detections) -> dict[int, tuple[float, float]]:
    """``tracker_id -> box centre`` for the confirmed Tracks present this frame."""
    if confirmed.tracker_id is None:
        return {}
    centers: dict[int, tuple[float, float]] = {}
    for i, tid in enumerate(confirmed.tracker_id):
        x1, y1, x2, y2 = confirmed.xyxy[i]
        centers[int(tid)] = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
    return centers


def _track_frame(
    byte_track: _ByteTracker, detections: sv.Detections
) -> tuple[sv.Detections, dict[int, int]]:
    """Run ByteTrack on the raw detections; return confirmed Tracks + the id-join map."""
    detections.data["_idx"] = np.arange(len(detections))
    confirmed = byte_track.update_with_detections(detections)
    return confirmed, _build_track_map(confirmed)


def _annotate_confirmed(
    frame: np.ndarray, confirmed: sv.Detections, ann: _TrackAnnotators
) -> np.ndarray:
    """Draw confirmed Tracks: trail + box + ``#id`` label (the ADR-0004 filtered view)."""
    scene = frame.copy()
    if confirmed.tracker_id is None or len(confirmed) == 0:
        return scene
    labels = [f"#{int(t)}" for t in confirmed.tracker_id]
    scene = ann.trace.annotate(scene, confirmed)
    scene = ann.mark.annotate(scene, confirmed)
    # sv.LabelAnnotator.annotate is mis-stubbed as PIL-only; it accepts/returns ndarray.
    labelled = ann.label.annotate(scene, confirmed, labels=labels)  # pyright: ignore
    return cast(np.ndarray, labelled)


@dataclass(frozen=True)
class _TrackRuntime:
    """Per-run tracking state, set together iff ``--track`` (keeps the loop branch-clean)."""

    byte_track: _ByteTracker
    ann: _TrackAnnotators
    slots: ZoomSlots | None  # None when --no-zoom


def _build_track_runtime(
    zoom: ZoomConfig, track: TrackConfig, frame_wh: tuple[int, int], fps: int
) -> _TrackRuntime:
    with warnings.catch_warnings():
        # sv.ByteTrack is deprecated (removed in supervision 0.30); we pin <0.30 and use it
        # per ADR-0006. Silence the FutureWarning so it doesn't pollute the run output.
        warnings.simplefilter("ignore", FutureWarning)
        byte_track = sv.ByteTrack(
            track_activation_threshold=track.activation,
            lost_track_buffer=track.buffer,
            frame_rate=fps,
        )
    slots = (
        ZoomSlots(zoom.max_panels, track.buffer, forced_id=zoom.track_id)
        if zoom.enabled
        else None
    )
    return _TrackRuntime(byte_track, _build_track_annotators(frame_wh), slots)
