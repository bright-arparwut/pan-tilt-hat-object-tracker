"""object_tracker — object detection + tracking over offline video.

YOLO (today) + optional sliced inference (the SAHI *technique*, via ``supervision``'s
``InferenceSlicer``) over a video file, producing an annotated video (boxes + a
picture-in-picture zoom inset) and a per-frame JSONL detections sidecar.

The package is split one module per pipeline stage (ADR-0009): ``config``, ``device``,
``detection``, ``tracking``, ``zoom``, ``sidecar``, ``pipeline``, ``cli``.
"""

from __future__ import annotations
