---
name: slicing-currently-broken
description: Sliced inference is NOT broken — the 2026-06-26 report was parameter misuse; guardrails now warn
metadata:
  node_type: memory
  type: project
  originSessionId: 1b485e4b-c8fb-424d-be61-faf05820ceff
---

**Resolved 2026-06-27.** The earlier "sliced inference is broken" report was a
misdiagnosis. `SlicedDetector` over `sv.InferenceSlicer` (supervision 0.29.1) works: the
`overlap_filter` (NMS/NMM) IS passed (`detection/yolo.py`) and merges/dedups across tiles
(verified — zero overlapping pairs at sane tile sizes). The old `overlap_filter_strategy`
arg name was renamed to `overlap_filter`; nothing is lost.

**What actually looked "broken":** `--slice-wh 100 100` on a 640×360 frame → ~40 tiles/frame
(~2 hrs on CPU), tiny tiles upscaled ~6× so small objects vanish (under-detection), and
objects larger than a tile fragment into adjacent partial boxes that NMS can't merge
("overlap frame"). Separately, the default `--slice-wh 640 640` is **intentionally** a no-op
on ≤640px frames — slicing is a documented 4K feature (ADR-0002; README/cheatsheet). Not bugs.

**Fix shipped:** `detection.slice_warnings()` + a CLI guardrail warn up front when `--slice-wh`
is degenerate — ≥ frame (no-op) or `< MIN_SLICE_PX` (128px; slow + fragmenting). No design
change; the 640 default and 4K-oriented behavior stand. See [[live-mode-design]] (Live still
never depends on slicing). The SAHI `get_sliced_prediction` migration idea was considered and
declined (loses concurrency + backend-agnostic slicing for a per-frame video path).
