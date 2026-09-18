"""Track-view annotators + the per-run track runtime (ADR-0012).

Identities come from the YOLO backend's ``track()`` (Ultralytics ``model.track()``), not an
in-loop tracker — this module does not *run* a tracker, it only draws the confirmed-Track
view (trail + box + ``#id``) and holds the per-run zoom slots.

That is ADR-0012 superseding ADR-0006. Read both before you write this file.
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
    """Compose the themed factory builders into the track bundle.

    All three use ``sv.ColorLookup.TRACK``, not ``CLASS``: under tracking the useful colour
    is per-identity, so the same object keeps one colour even as its class confidence wobbles.
    """
    raise NotImplementedError("Week 6 — see learn/curriculum/week-06-bytetrack.md")


def _present_centers(confirmed: sv.Detections) -> dict[int, tuple[float, float]]:
    """``tracker_id -> box centre`` for the confirmed Tracks present this frame.

    Coerce each centre to a plain Python ``float``. ``xyxy`` is numpy (float32 out of
    ``model.track()``), and in week 11 these centres flow into the turret wire's
    ``json.dumps``, which raises "float32 is not JSON serializable" — crashing the control
    loop mid-run, with a motor moving. Fix it here, at the source. There is a given test.
    """
    raise NotImplementedError("Week 6 — see learn/curriculum/week-06-bytetrack.md")


def _annotate_confirmed(
    frame: np.ndarray, confirmed: sv.Detections, ann: _TrackAnnotators
) -> np.ndarray:
    """Draw confirmed Tracks: trail + box + ``#id`` label (the ADR-0004 filtered view).

    Draw on a **copy** — never mutate the caller's frame. Order matters: trail first so
    boxes and labels sit on top. With no ids present, return the copy unchanged rather than
    letting an annotator choke on an empty/idless ``Detections``.
    """
    raise NotImplementedError("Week 6 — see learn/curriculum/week-06-bytetrack.md")


@dataclass(frozen=True)
class _TrackRuntime:
    """Per-run tracking state, set together iff ``--track`` (keeps the loop branch-clean)."""

    ann: _TrackAnnotators
    slots: ZoomSlots | None  # None when --no-zoom


def _build_track_runtime(
    zoom: ZoomConfig, track: TrackConfig, frame_wh: tuple[int, int]
) -> _TrackRuntime:
    """Build the per-run tracking state in one place, so the loop has one ``if``, not three."""
    raise NotImplementedError("Week 7 — see learn/curriculum/week-07-zoom-slots.md")
