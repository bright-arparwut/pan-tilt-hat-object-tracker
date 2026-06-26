"""Detections sidecar: serialise per-frame detections to plain dicts (ADR-0001)."""

from __future__ import annotations

import supervision as sv


def detection_records(
    detections: sv.Detections, track_map: dict[int, int] | None = None
) -> list[dict]:
    """Serialise detections to plain dicts (source-pixel xyxy).

    Every raw detection is emitted (ADR-0004). When ``track_map`` is given (``--track``),
    each row gains ``"track_id"`` — the int from the row's confirmed Track, or ``null`` for
    recall-first noise dropped by ByteTrack (ADR-0006). When ``None`` (``--no-track``) the
    key is omitted, leaving today's schema byte-for-byte unchanged.
    """
    if len(detections) == 0:
        return []
    names = detections.data.get("class_name") if detections.data else None
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
        if track_map is not None:
            tid = track_map.get(i)
            record["track_id"] = int(tid) if tid is not None else None
        records.append(record)
    return records
