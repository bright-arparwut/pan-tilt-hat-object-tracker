# 06 — CLI wiring and end-to-end run

Status: done (implemented in d75e61c on feat/bird-detection-loop)

## Goal

Wire all flags into the entry point and validate the full loop on the test clip.

## Tasks

- Parse the full CLI surface (PRD §CLI surface) with sensible defaults.
- Compose loop: frame generator → `detect()` → annotate (+ zoom) → `VideoSink` + sidecar.
- Default output/sidecar paths derived from `--source` when omitted.
- Validate inputs at the boundary (source exists/opens, slice-wh positive, etc.).

## Acceptance (mirrors PRD §Acceptance criteria)

1. `--no-slice` on test clip → annotated `.mp4` + `.jsonl` (one line/frame).
2. `--slice --slice-wh 256 256` → same artifact shapes.
3. `--weights custom.pt` → all classes kept.
4. Sidecar validates; `xyxy` in source pixels.
5. Zoom inset follows top-confidence detection, smoothed.
6. Bad `--source` → non-zero exit, clear message, no partial outputs.

## Depends on

02, 03, 04, 05.

## Refs

PRD §Acceptance criteria.
