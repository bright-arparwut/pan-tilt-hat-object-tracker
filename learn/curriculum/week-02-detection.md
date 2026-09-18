# Week 2 — Object detection & the Detector seam

**Hours:** 7 · **Where:** Mac · **Milestone:** print every detection in a clip

## Why this week

The seam comes before the model. You write `Detector` — a one-method Protocol — *first*, and
only then a YOLO class that satisfies it. That ordering is the entire reason this project can
swap detection backends without touching the loop, and it's the habit worth stealing.

## Concepts

- **What a detection is:** `xyxy` (absolute pixel corners), `confidence` (float 0–1),
  `class_id` (int index into the model's class names). That's it. Everything downstream —
  annotation, tracking, the sidecar, the turret — is a transformation of that tuple.
- **NMS (non-maximum suppression):** why one object produces many raw boxes, and how
  IoU-thresholded suppression collapses them. You'll meet IoU again in week 5 as the
  *matching* metric — same formula, different job.
- **Confidence as a recall/precision dial.** This project sets `--conf 0.15`, which is
  *deliberately noisy*. Understand why before you "fix" it: the tracker is the false-positive
  filter (ADR-0004), not the threshold.
- **Device selection:** `cpu` vs `mps` (Apple Silicon) vs `cuda`. On your MacBook, `mps`.
  Know how to detect it and how to fall back.
- **COCO classes:** 80 of them, `bird` is 14, `person` 0, `car` 2. Custom weights have their own.

Read: the Ultralytics predict docs (via Context7 or the primary docs), `supervision`'s
`Detections.from_ultralytics`, `typing.Protocol`.

## Sessions

**Session 1 (2h) — the seam.** `detection/base.py`: the `Detector` Protocol. Two lines of
code, an hour of thought. Write `detection/__init__.py`'s `build_detector` as a stub that
returns a YOLO backend directly (the slicing branch comes in week 4). Then `device.py`.

**Session 2 (3h) — the backend.** `detection/yolo.py`: `YoloDetector`. Load the weights once
in `__init__`, not per frame. Pass `conf`, `classes`, `device` to the model. Convert the
result to `sv.Detections`. Run it on a still image first, print the array shapes, *look at
the numbers* before you wire it into the loop.

**Session 3 (2h) — into the loop.** Wire `detector.detect(frame)` into `pipeline.run`. Print
the per-frame detection count. Watch it on a real clip; sanity-check a few boxes by eye.

## Files you implement

| File | What |
|---|---|
| `object_tracker/detection/base.py` | `Detector` Protocol (leave `TrackingDetector` for week 6) |
| `object_tracker/detection/yolo.py` | `YoloDetector` (leave `SlicedDetector` for week 4) |
| `object_tracker/detection/__init__.py` | `build_detector`, no slicing branch yet |
| `object_tracker/device.py` | `resolve_device` |
| `object_tracker/pipeline.py` | add the detect call |

## Tests you're given

`tests/test_detection.py::test_yolo_detector_passes_conf_and_classes_to_the_model`,
`::test_yolo_detector_returns_sv_detections`,
`tests/test_detection.py::test_resolve_device_prefers_available_accelerator`

Note they use a **fake model**, not real weights. That's the lesson: your backend must be
testable without a 100MB `.pt` file and a GPU.

## Tests you write

- `classes=None` keeps every class (ADR-0008's "general by default")
- An empty frame → `len(detections) == 0`, not a crash
- `resolve_device("cpu")` when an accelerator *is* available (explicit wins)

## Milestone

```bash
uv run python -m object_tracker.cli --source ../footage/clip.mp4 --weights yolo11n.pt
# prints per-frame detection counts
```

Start with `yolo11n.pt` (nano), not `yolo11x.pt`. It's 20× faster and you're debugging
plumbing, not chasing accuracy.

## ADR to write

**ADR-0009 (part 1) — a backend-agnostic Detector seam.** Why a Protocol and not a base
class? What would it cost you to skip the seam and call YOLO directly in the loop?

## Stuck?

`.scratch/bird-detection-loop/issues/03-detection-step-slicing-toggle.md` is the original
spec. The root repo's `detection/base.py` is 30 lines — resist reading it until you've
written yours.
