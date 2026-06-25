# 02 — Backend-agnostic Detector seam + SlicedDetector decorator

Status: ready-for-agent

## Goal

Turn `make_detector` into a named, backend-agnostic `Detector` interface with the YOLO
backend as one implementation and **slicing as a decorator over any Detector**. Behaviour
stays byte-identical; this only reshapes the seam so a future DETR/RF-DETR backend can slot
in without touching the pipeline. Implement **YOLO only** (YAGNI — no DETR code).

## Decisions (from grilling session)

- **`Detector` is a `Protocol`** — `detect(frame: np.ndarray) -> sv.Detections`. The pipeline
  depends only on this; `pipeline.py` never imports YOLO (ADR-0009).
- **`YoloDetector` owns conf, classes, device** — a `Detector Backend`; it honours the class
  filter however it likes (YOLO's native `classes=` arg). Wraps today's `infer` callback.
- **`SlicedDetector(base: Detector, slice_wh, overlap_wh, overlap_filter, thread_workers)`** —
  a `Detector` that runs `base.detect` over slices via `sv.InferenceSlicer` (callback =
  `base.detect`). Backend-agnostic; **revises ADR-0003's** slicing-on-the-YOLO-path
  assumption.
- **`build_detector(cfg) -> Detector`** factory (in `detection/__init__.py`): build the
  backend, wrap in `SlicedDetector` iff `cfg.use_slicing`. `pipeline.run` calls
  `detector.detect(frame)` — still slice-agnostic.

## Tasks

- `detection/base.py` — define `Detector` Protocol; optionally a `Detection`-shape note. Keep
  `_ByteTracker`-style structural typing conventions already in the repo.
- `detection/yolo.py` — `YoloDetector` (holds the `YOLO` model + conf/classes/device; wraps
  the per-image `infer`), `SlicedDetector` (wraps a `Detector`; builds the `InferenceSlicer`
  with px overlap derived from the resolution-relative ratio, as today), `_overlap_filter`.
- `detection/__init__.py` — `build_detector(cfg)` factory; export `Detector`, `YoloDetector`,
  `SlicedDetector`, `build_detector`.
- `pipeline.py` — replace `make_detector(model, cfg)` + `model = YOLO(weights)` with
  `detector = build_detector(cfg)`; drop the direct `YOLO`/`make_detector` import.
- Consider splitting `DetectConfig` into the fields the backend needs vs. the slicer needs,
  or keep `DetectConfig` whole and let `build_detector` read the relevant fields (simplest —
  prefer this unless it reads badly).
- Tests: `test_detection.py` — `SlicedDetector` over a fake `Detector` (a stub returning a
  known `sv.Detections`) calls the base per slice and merges; `build_detector` returns a bare
  backend under `--no-slice` and a wrapped one under `--slice`. Equivalence: sliced path
  yields the same detections as the pre-refactor `make_detector` on a fixed input.

## Acceptance

1. `pipeline.py` imports the `Detector` Protocol, not `YOLO`.
2. `SlicedDetector` produces byte-identical detections to the old sliced `make_detector` on a
   fixed clip/seed; `--no-slice` uses the bare `YoloDetector`.
3. A fake non-YOLO `Detector` can be wrapped by `SlicedDetector` in a test (proves
   backend-agnosticism) without importing ultralytics.
4. `uv run pytest` green; smoke run unchanged from 01.

## Depends on

01 (package split).

## Refs

ADR-0009 (Detector seam, slicing decorator), ADR-0003 (sliced inference via supervision —
revised). PRD §The Detector seam.
