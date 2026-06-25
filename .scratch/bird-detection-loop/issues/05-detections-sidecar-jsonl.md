# 05 — Detections sidecar (JSONL)

Status: done (implemented in d75e61c on feat/bird-detection-loop)

## Goal

Persist every detection per frame as the tracker-ready handoff (ADR-0001).

## Tasks

- Open `--sidecar` (default `<source>.detections.jsonl`) for append-only writing.
- Per frame, write one JSON line:
  `{"frame": i, "detections": [{"xyxy": [x1,y1,x2,y2], "conf": f, "cls": int, "name": str}, ...]}`.
- `xyxy` are pixel coords in **source** resolution (not inset/annotated coords).
- Frames with zero detections still emit a line with `"detections": []`.
- Flush safely; ensure the file is valid JSONL even if the run is interrupted mid-stream
  (line-buffered writes).

## Acceptance

- One line per processed frame; lines validate against the schema.
- Coordinates round-trip to source pixels; empty frames present.

## Depends on

03.

## Refs

ADR-0001. CONTEXT.md (Detections Sidecar). PRD §Outputs.
