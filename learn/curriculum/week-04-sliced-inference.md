# Week 4 — Sliced inference (the SAHI technique)

**Hours:** 7 · **Where:** Mac · **Milestone:** find small objects in a 4K clip that plain inference misses

## Why this week

Two payoffs, and the second matters more.

**The CV payoff:** YOLO resizes every input to ~640px. A bird occupying 30px in a 4K frame
becomes 5px after that downscale — below the size any detector can resolve. Slicing runs the
model on overlapping native-resolution tiles instead, so the bird stays 30px. This single
technique is the difference between "my model doesn't work on drone footage" and a working
system.

**The design payoff:** `SlicedDetector` is a **decorator over a Protocol**. It *is* a
`Detector`, and it *wraps* a `Detector`. That's why a future RF-DETR backend gets slicing for
free without a line of slicing code. This is the week the week-2 seam pays for itself — feel
that, and you'll reach for Protocols for the rest of your career.

## Concepts

- **Why small objects vanish:** letterbox resize, effective pixels-on-target, the ~10px floor
  below which a detector has nothing to work with.
- **Tiling:** slice size, overlap ratio (why overlap at all?), and what happens to an object
  that straddles a tile boundary.
- **Merge strategy — NMS vs NMM.** NMS *suppresses* the lower-confidence duplicate; NMM
  *merges* the boxes. Which is right for an object fragmented across two tiles?
- **The degenerate parameter space.** A tile ≥ the frame does nothing. A tile far smaller than
  the frame is slow *and* wrong (heavy upscale kills small objects; objects bigger than a tile
  fragment). `slice_warnings` exists because the slicer can't fix a bad parameter — it can
  only tell you. **Guardrails-not-limits** is a pattern worth stealing.
- **Cost.** Slicing means tens of forward passes per frame. Understand `thread_workers` and
  why this path is offline-only.

Read: the SAHI paper (skim the figures — they make the point instantly), `supervision`'s
`InferenceSlicer` API.

## Sessions

**Session 1 (2h) — see the problem.** Before writing any slicing code: take a 4K clip, run
week 2's detector, count detections. Then crop a 640×640 region containing a small object, run
the detector on the crop alone, count again. **Measure the gap yourself.** This is the most
important hour of the week.

**Session 2 (3h) — the decorator.** `SlicedDetector`. The `_overlap_px` helper (ratio → absolute
px, because `InferenceSlicer` wants absolute and you want resolution-relative flags). Then
`build_detector`'s branch: slicing wraps, tracking doesn't.

**Session 3 (2h) — guardrails + CLI.** `slice_warnings`, and the full CLI flag surface for
slicing. Re-run session 1's 4K clip through the slicer and compare against your measurement.

## Files you implement

| File | What |
|---|---|
| `object_tracker/detection/yolo.py` | `SlicedDetector` |
| `object_tracker/detection/__init__.py` | `_overlap_px`, `slice_warnings`, the `build_detector` branch |
| `object_tracker/cli.py` | `--slice/--no-slice`, `--slice-wh`, `--overlap-ratio`, `--overlap-filter`, `--thread-workers` |

## Tests you're given

`tests/test_detection.py::test_sliced_detector_calls_the_wrapped_detector_per_tile`,
`::test_slice_warnings_flags_a_tile_larger_than_the_frame`,
`::test_slice_warnings_is_silent_for_a_sane_subdividing_tile`

## Tests you write

- `_overlap_px` rounding at the edges
- `slice_warnings` for a tile *far* smaller than the frame (the second warning arm)
- `build_detector` returns an unwrapped backend when `use_slicing=False`
- `SlicedDetector` satisfies `Detector` (a `isinstance`-free structural check)

## Milestone

```bash
uv run track --source clip_4k.mp4 --slice --slice-wh 640 640     # more small objects
uv run track --source clip_4k.mp4 --no-slice                      # fewer
```

Compare the two sidecar files. The delta is the whole point of the week.

## ADR to write

Two, and they're a pair:

- **ADR-0002 — retain the SAHI *technique* for high-res footage.** When is slicing worth 30×
  the compute?
- **ADR-0003 — implement it via `supervision`'s `InferenceSlicer`, not the `sahi` package.**
  A real dependency decision. What are you trading away?

## Stuck?

`.scratch/bird-detection-loop/issues/03-detection-step-slicing-toggle.md`. The root repo's
`detection/__init__.py` has the warning logic fully commented.
