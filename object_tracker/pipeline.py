"""The frame loop: detect -> (track) -> annotate + zoom -> sidecar + video sink."""

from __future__ import annotations

import json

import supervision as sv
from tqdm import tqdm

from .config import DetectConfig, RunPaths, TrackConfig, ZoomConfig
from .detection import build_detector
from .sidecar import detection_records
from .tracking import (
    _annotate_confirmed,
    _build_track_runtime,
    _present_centers,
    _track_frame,
)
from .zoom import _confidence_zoom, draw_identity_panels


def run(
    cfg: DetectConfig, paths: RunPaths, zoom: ZoomConfig, track: TrackConfig
) -> None:
    video_info = sv.VideoInfo.from_video_path(str(paths.source))
    frame_wh = video_info.resolution_wh

    detector = build_detector(cfg)
    detect = detector.detect
    box_annotator = sv.BoxAnnotator(
        thickness=sv.calculate_optimal_line_thickness(resolution_wh=frame_wh)
    )
    rt = (
        _build_track_runtime(zoom, track, frame_wh, round(video_info.fps))
        if track.enabled
        else None
    )

    paths.output.parent.mkdir(parents=True, exist_ok=True)
    paths.sidecar.parent.mkdir(parents=True, exist_ok=True)

    frames = sv.get_video_frames_generator(str(paths.source))
    zoom_center = None
    with sv.VideoSink(str(paths.output), video_info) as sink, open(
        paths.sidecar, "w", buffering=1
    ) as sidecar:
        for idx, frame in enumerate(tqdm(frames, total=video_info.total_frames, unit="f")):
            detections = detect(frame)
            if rt is not None:
                confirmed, track_map = _track_frame(rt.byte_track, detections)
                records = detection_records(detections, track_map)
                annotated = _annotate_confirmed(frame, confirmed, rt.ann)
                if rt.slots is not None:
                    renders = rt.slots.update(_present_centers(confirmed), idx)
                    annotated = draw_identity_panels(
                        annotated, frame, renders, zoom.size, frame_wh, rt.slots.capacity
                    )
            else:
                records = detection_records(detections)
                annotated = box_annotator.annotate(scene=frame.copy(), detections=detections)
                if zoom.enabled:
                    zoom_center = _confidence_zoom(
                        annotated, frame, detections, zoom, frame_wh, zoom_center
                    )
            sidecar.write(json.dumps({"frame": idx, "detections": records}) + "\n")
            sink.write_frame(annotated)
