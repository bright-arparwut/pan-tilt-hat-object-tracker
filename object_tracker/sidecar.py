"""Detections sidecar: serialise per-frame detections to plain dicts (ADR-0001)."""

from __future__ import annotations

import supervision as sv


def frame_record(idx: int, records: list[dict], ts: float | None = None) -> dict:
    """Wrap one frame's detection records into the JSONL object the sidecar writes.

    Offline (``ts=None``) keeps today's schema **byte-for-byte**: ``{"frame", "detections"}``.
    Live passes a capture ``ts`` (epoch seconds) — inserted between ``frame`` and
    ``detections`` — because on a Live Source the frame index counts *received* frames, not
    wall-clock time (ADR-0010 §Throughput).
    """
    record: dict = {"frame": idx}
    if ts is not None:
        record["ts"] = ts
    record["detections"] = records
    return record


def detection_records(
    detections: sv.Detections, with_track_id: bool = False
) -> list[dict]:
    """Serialise detections to plain dicts (source-pixel xyxy).

    When ``with_track_id`` (``--track``), each row gains ``"track_id"`` read straight from the
    detections' own ``tracker_id`` (ids come pre-attached from ``model.track()`` via
    ``from_ultralytics`` — ADR-0012), or ``null`` when the frame carries no ids. When
    ``False`` (``--no-track``) the key is omitted, leaving today's schema byte-for-byte
    unchanged and recording every raw detection (ADR-0004).
    """
    if len(detections) == 0:
        return []
    names = detections.data.get("class_name") if detections.data else None
    tracker_id = detections.tracker_id if with_track_id else None
    records = []
    for i in range(len(detections)):
        x1, y1, x2, y2 = (round(float(v), 1) for v in detections.xyxy[i])
        conf = detections.confidence[i] if detections.confidence is not None else None
        cls = detections.class_id[i] if detections.class_id is not None else None
        record = {
            "xyxy": [x1, y1, x2, y2],
            "conf": round(float(conf), 4) if conf is not None else None,
            "cls": int(cls) if cls is not None else None,
            "name": str(names[i]) if names is not None else None,
        }
        if with_track_id:
            tid = tracker_id[i] if tracker_id is not None else None
            record["track_id"] = int(tid) if tid is not None else None
        records.append(record)
    return records
