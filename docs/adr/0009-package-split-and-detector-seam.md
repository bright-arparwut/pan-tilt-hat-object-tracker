# Split the single script into an `object_tracker` package behind a backend-agnostic Detector seam

The pipeline outgrew its single-file form. We split `detect_birds.py` into an
`object_tracker/` package with one module per pipeline stage, and we promote the detector
to a named, backend-agnostic interface so a second detection model can slot in without
touching the rest of the pipeline. This **reverses the PRD's "a single Python script"
constraint** — that constraint bought a trivial install/run story early on, but at ~700
lines spanning detection, slicing, tracking, zoom, sidecar, and CLI it now hides the seams
the project needs next (swappable detectors, custom classes).

## Package shape

```
object_tracker/
  __init__.py
  config.py        # *Config dataclasses + resolution-relative constants
  device.py        # resolve_device (cuda -> mps -> cpu)
  detection/
    base.py        # Detector Protocol: detect(frame) -> sv.Detections
    yolo.py        # YoloDetector backend + SlicedDetector decorator
  tracking.py      # sv.ByteTrack wrapper, raw-row -> track_id join, annotators
  zoom.py          # confidence-mode + identity-mode (ZoomSlots) insets
  sidecar.py       # detection_records (JSONL rows)
  pipeline.py      # run() — the Detection Loop
  cli.py           # build_parser, validation, main
```

## The Detector seam (the load-bearing decision)

- **`Detector` is a `Protocol`** — `detect(frame: np.ndarray) -> sv.Detections`. The pipeline
  depends only on this; it never imports YOLO. A `Detector Backend` (e.g. `YoloDetector`)
  owns its own confidence, class filter, and device — how it honours those is its business
  (YOLO uses native args; a future DETR backend might post-filter).
- **Slicing is a decorator, not a backend concern.** `SlicedDetector(base: Detector, ...)`
  wraps *any* Detector and runs it over the frame's Slices via `sv.InferenceSlicer`
  (callback = `base.detect`). This **revises ADR-0003's** assumption that slicing lives on
  the YOLO path: the SAHI *technique* is genuinely backend-agnostic, so writing it once as a
  decorator means a future DETR/RF-DETR backend gets sliced inference for free.
- **Assembly** lives in a small `build_detector(cfg) -> Detector` factory: construct the
  backend, then wrap it in `SlicedDetector` iff `--slice`. The loop just calls
  `detector.detect(frame)` — still slice-agnostic, preserving the ADR-0002/0003 invariant
  that nothing downstream branches on slicing.

## Considered options

- **Keep the single file** — rejected: the seams the project needs next (backends, custom
  classes) are invisible in a 700-line module; the install-simplicity win no longer pays for
  the navigation cost.
- **Slicing inside each backend** (`YoloDetector(use_slicing=...)`) — rejected: every future
  backend would re-implement the same `InferenceSlicer` glue.
- **A thin detector + slicing/filtering as pipeline stages** — rejected: it spreads detection
  logic across `pipeline.py` and weakens the "a Detector is a thing you call" mental model.

## Consequences

- **No back-compat shim.** Pre-1.0 personal project, clean break: there is no
  `detect_birds` module and no `detect-birds` console alias after the rename (ADR-0008 / the
  rename phase). Tests import from `object_tracker.*`.
- Behaviour is otherwise **unchanged** by the split itself — it is a structural move; the
  detector seam and slicing decorator produce byte-identical detections to the old
  `make_detector`.
- `pyproject.toml` wheel target moves from the single module to the package; the console
  entry point becomes `object_tracker.cli:main`.
