"""The frame loop: detect -> (track) -> annotate + zoom -> sidecar + frame sink.

The loop depends only on the ``FrameSource`` / ``FrameSink`` seams (ADR-0010) and the
``Detector`` seam (ADR-0009) — never on files or cv2 directly — so the same loop serves an
Offline file and a Live camera/stream. Termination is unified: it ends when the source is
exhausted **or** the sink returns ``False`` (e.g. the viewer quits). A single ``finally``
releases the source, closes the sink, and closes the sidecar on every exit path (EOF, ``q``,
``Ctrl-C``, or an error mid-loop).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import cast

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
    info = source.info
    frame_wh = info.resolution_wh

    detection_annotator = build_detection_annotator(frame_wh)
    rt = _build_track_runtime(zoom, track, frame_wh) if track.enabled else None
    # Under --track the build guarantees a TrackingDetector (ADR-0012); never wrapped by the
    # slicing decorator, so model.track() is callable here.
    tracking_detector = cast(TrackingDetector, detector) if track.enabled else None

    # A Live (unbounded) source has no frame total; its frame index isn't a wall-clock, so
    # its sidecar rows carry a capture ts (ADR-0010 §Throughput).
    is_live = info.total_frames is None

    sidecar = None
    if sidecar_path is not None:
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        sidecar = open(sidecar_path, "w", buffering=1)

    zoom_center = None
    try:
        for idx, frame in enumerate(tqdm(source, total=info.total_frames, unit="f")):
            ts = time.time() if is_live else None
            if rt is not None and tracking_detector is not None:
                confirmed = tracking_detector.track(frame)
                records = detection_records(confirmed, with_track_id=True)
                annotated = _annotate_confirmed(frame, confirmed, rt.ann)
                if rt.slots is not None:
                    renders = rt.slots.update(_present_centers(confirmed), idx)
                    annotated = draw_identity_panels(
                        annotated, frame, renders, zoom.size, frame_wh, rt.slots.capacity
                    )
            else:
                detections = detector.detect(frame)
                records = detection_records(detections)
                annotated = detection_annotator.annotate(scene=frame.copy(), detections=detections)
                if zoom.enabled:
                    zoom_center = _confidence_zoom(
                        annotated, frame, detections, zoom, frame_wh, zoom_center
                    )
            if sidecar is not None:
                sidecar.write(json.dumps(frame_record(idx, records, ts)) + "\n")
            if not sink.show(annotated):
                break
    finally:
        # Release every resource even if an earlier teardown step raises (e.g. a window
        # close failing must not strand the camera handle).
        try:
            sink.close()
        finally:
            try:
                source.release()
            finally:
                if sidecar is not None:
                    sidecar.close()
