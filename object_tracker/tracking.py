"""Track-view annotators + the per-run track runtime (ADR-0012).

Identities now come from the YOLO backend's ``track()`` (Ultralytics ``model.track()``),
not an in-loop ``sv.ByteTrack`` — this module no longer runs a tracker, it only draws the
confirmed-Track view (trail + box + ``#id``) and holds the per-run zoom slots.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

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


def _present_centers(confirmed: sv.Detections) -> dict[int, tuple[float, float]]:
    """``tracker_id -> box centre`` for the confirmed Tracks present this frame."""
    if confirmed.tracker_id is None:
        return {}
    centers: dict[int, tuple[float, float]] = {}
    for i, tid in enumerate(confirmed.tracker_id):
        x1, y1, x2, y2 = confirmed.xyxy[i]
        # float(...) honours the annotated python-float contract: xyxy is numpy (float32 from
        # model.track()), and a numpy centre flows into the turret wire's json.dumps, which
        # raises "float32 is not JSON serializable" (ADR-0013).
        centers[int(tid)] = (float((x1 + x2) / 2.0), float((y1 + y2) / 2.0))
    return centers


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

    ann: _TrackAnnotators
    slots: ZoomSlots | None  # None when --no-zoom


def _build_track_runtime(
    zoom: ZoomConfig, track: TrackConfig, frame_wh: tuple[int, int]
) -> _TrackRuntime:
    slots = (
        ZoomSlots(zoom.max_panels, track.buffer, forced_id=zoom.track_id)
        if zoom.enabled
        else None
    )
    return _TrackRuntime(_build_track_annotators(frame_wh), slots)
