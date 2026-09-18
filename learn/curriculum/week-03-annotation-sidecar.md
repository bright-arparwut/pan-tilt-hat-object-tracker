# Week 3 — Annotation & the sidecar

**Hours:** 6 · **Where:** Mac · **Milestone:** `clip.annotated.mp4` + `clip.detections.jsonl`

## Why this week

One detection stream, two consumers with opposite needs. A **human** needs boxes drawn at a
readable thickness. A **machine** needs a lossless, append-only record it can replay. Conflate
them and you get a video you can't query and a log you can't watch.

This is also where you meet the project's opinion about configuration: some things are flags,
some things are constants, and the line between them is a design decision (ADR-0011).

## Concepts

- **Resolution-relative styling.** A 2px box outline is fine at 640p and invisible at 4K.
  `supervision` ships `calculate_optimal_line_thickness` / `calculate_optimal_text_scale` for
  this. Understand why the project multiplies them by `0.5`.
- **JSONL** (one JSON object per line) vs a single JSON array: why the former is the right
  shape for a per-frame record. What does it buy you if the process crashes at frame 9,000?
- **Schema stability.** Look at `sidecar.frame_record`: the `ts` key is inserted *between*
  `frame` and `detections`, and only in Live mode. Why does the docstring say
  "byte-for-byte"? Who would care?
- **Flags vs constants.** The `Appearance` block in `config.py` is ~20 constants that are
  deliberately **not** CLI flags. Read ADR-0011's reasoning. Do you agree?
- **`float()` coercion at boundaries.** `xyxy` is numpy float32. `json.dumps` cannot
  serialise it. Where's the right place to fix that — and why does the project fix it in
  *two* places?

## Sessions

**Session 1 (2h) — the sidecar.** `sidecar.py` is only 53 lines and entirely pure. Write it
first; it's the easiest complete module in the project and a good confidence win. Get the
`round()` precision decisions right (why 1 decimal for pixels, 4 for confidence?).

**Session 2 (2.5h) — annotators.** `annotators.py`: a factory that reads the `Appearance`
constants and builds `supervision` annotators. The wrinkle: the ten `DetectionStyle` variants
**don't share a constructor**, so the factory can't be a one-liner dict lookup. Work out how
to handle that cleanly.

**Session 3 (1.5h) — wire it up.** Annotate in the loop, write the sidecar line, produce both
outputs. Open the mp4. Open the jsonl. Check they agree on frame 100.

## Files you implement

| File | What |
|---|---|
| `object_tracker/sidecar.py` | `frame_record`, `detection_records` |
| `object_tracker/annotators.py` | `build_detection_annotator`, `build_label_annotator`, `build_trace_annotator` |
| `object_tracker/pipeline.py` | annotate + write the sidecar line |
| `object_tracker/cli.py` | `_derive_paths`, minimal parser |

## Tests you're given

`tests/test_sidecar.py::test_frame_record_offline_schema_has_no_ts`,
`::test_detection_records_round_trips_xyxy_conf_and_class`,
`tests/test_annotators.py::test_thickness_scales_with_frame_size`

## Tests you write

- `detection_records` on empty detections → `[]`
- A detection whose `confidence` is `None` (some backends omit it)
- `frame_record` *with* a `ts` — key order matters, assert it
- Each `DetectionStyle` variant builds without raising (a cheap, high-value loop)

## Milestone

```bash
uv run track --source ../footage/clip.mp4 --weights yolo11n.pt
# wrote ../footage/clip.annotated.mp4
# wrote ../footage/clip.detections.jsonl
head -1 ../footage/clip.detections.jsonl | python -m json.tool
```

**End of month 1: you have a working offline object detector.** Take a moment.

## ADR to write

**ADR-0011 — appearance as in-code constants, not CLI flags.** Argue it both ways before you
pick. What's the cost of 20 more flags? What's the cost of needing a code edit to change a
colour?

## Stuck?

`.scratch/bird-detection-loop/issues/04-annotation-boxes-zoom-inset.md` and
`05-detections-sidecar-jsonl.md`.
