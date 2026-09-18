"""The frame loop: detect -> (track) -> annotate + zoom -> sidecar + frame sink.

The loop depends only on the ``FrameSource`` / ``FrameSink`` seams (ADR-0010) and the
``Detector`` seam (ADR-0009) — never on files or cv2 directly — so the same loop serves an
Offline file and a Live camera/stream. Termination is unified: it ends when the source is
exhausted **or** the sink returns ``False`` (e.g. the viewer quits).

A single ``finally`` releases the source, closes the sink, and closes the sidecar on **every**
exit path (EOF, ``q``, ``Ctrl-C``, or an error mid-loop). Note this needs *nested* finallys,
not one block: if closing the window raises, the camera handle must still be released.

This file grows every month:
  week 1  — the bare read → sink loop, no detector
  week 2  — detect()
  week 3  — annotate + the sidecar line
  week 6  — the tracking branch (track() instead of detect())
  week 7  — identity zoom panels
  week 8  — the is_live / capture-ts branch
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import cast

import supervision as sv
from tqdm import tqdm

from .annotators import build_detection_annotator
from .config import TrackConfig, ZoomConfig
from .detection import Detector, TrackingDetector
from .sidecar import detection_records, frame_record
from .sinks import FrameSink
from .sources import FrameSource
from .tracking import (
    _annotate_confirmed,
    _build_track_runtime,
    _present_centers,
)
from .zoom import _confidence_zoom, draw_identity_panels


def run(
    detector: Detector,
    source: FrameSource,
    sink: FrameSink,
    zoom: ZoomConfig,
    track: TrackConfig,
    sidecar_path: Path | None = None,
) -> None:
    """Run the detection loop to completion.

    Shape of the body you are building toward:

      1. Read ``source.info`` once — resolution sizes the annotators, ``total_frames``
         sizes the progress bar (``None`` for a Live source).
      2. Build per-run state before the loop: the annotators, the track runtime (only under
         ``--track``), the sidecar file handle.
      3. Per frame: detect *or* track → serialise records → annotate → write the sidecar
         line → ``sink.show(annotated, tracks)``; ``break`` on a falsey return.
      4. ``finally``: close the sink, release the source, close the sidecar — each
         independently, so one failure cannot strand the others.

    Under ``--track`` the build guarantees a ``TrackingDetector`` (ADR-0012) that the slicing
    decorator never wrapped, so ``model.track()`` is callable — ``cast`` is how you tell the
    type checker what the builder already guarantees.
    """
    raise NotImplementedError("Week 1 — see learn/curriculum/week-01-frame-io.md")
