# 01 — Split detect_birds.py into the object_tracker package (pure move)

Status: ready-for-agent

## Goal

Move the single `detect_birds.py` into an `object_tracker/` package, one module per
pipeline stage, with **zero behaviour change**. This is the mechanical move; the detector
seam (02), the bird-default drop (03), and the rename (04) come after. To keep this phase a
pure structural move, the console script and project name stay `detect-birds` /
`yolo-bytetrack-sot` for now (renamed in 04).

## Decisions (from grilling session)

- **By-stage modules + a `detection/` subpackage** (ADR-0009). Layout:
  `config.py`, `device.py`, `detection/base.py`, `detection/yolo.py`, `tracking.py`,
  `zoom.py`, `sidecar.py`, `pipeline.py`, `cli.py`.
- **Clean break, no shim** — there is no `detect_birds.py` left behind and no re-export
  module. Tests are rewired to `object_tracker.*` in this phase.

## Tasks

- Create `object_tracker/` and move code into stage modules, preserving function bodies:
  - `config.py` — `DetectConfig`, `RunPaths`, `TrackConfig`, `ZoomConfig` + the
    resolution-relative constants (`COCO_BIRD_CLASS_ID`, `DEFAULT_*`, `ZOOM_*`).
  - `device.py` — `resolve_device`.
  - `detection/yolo.py` — `make_detector`, `_overlap_filter` (the `Detector` Protocol in
    `detection/base.py` is introduced in 02; for now `detection/__init__.py` can re-export
    `make_detector`).
  - `tracking.py` — `_ByteTracker`, `_TrackAnnotators`, `_build_track_annotators`,
    `_build_track_map`, `_present_centers`, `_track_frame`, `_annotate_confirmed`,
    `_build_track_runtime`, `_TrackRuntime`.
  - `zoom.py` — `top_centers`, EMA/centre helpers, `draw_zoom_panels`, `_draw_one_panel`,
    `SlotRender`, `ZoomSlots`, identity drawers, `_confidence_zoom`.
  - `sidecar.py` — `detection_records`.
  - `pipeline.py` — `run`.
  - `cli.py` — `build_parser`, `validation_error`, `_resolve_classes`, `_derive_paths`,
    `main`, plus `if __name__ == "__main__"`.
- `pyproject.toml`: wheel target `include = ["detect_birds.py"]` → `packages = ["object_tracker"]`
  (hatch); console entry `detect-birds = "object_tracker.cli:main"` (name kept this phase).
- Rewire tests: split `tests/test_detect_birds.py` / `tests/test_tracking.py` to import from
  the new modules (`from object_tracker import cli, zoom, sidecar, tracking, ...`). Keep the
  same assertions. Mirror modules where it reads cleanly (`test_zoom.py`, `test_sidecar.py`,
  `test_cli.py`, `test_tracking.py`).

## Acceptance

1. `uv run pytest` green with **no assertion changes** (only import paths moved).
2. `object_tracker/` has the module tree above; no module exceeds ~200 lines.
3. A smoke run (`--classes 14 --no-slice` on the test clip) produces byte-identical
   annotated video + sidecar to pre-move.
4. No `detect_birds.py` remains; nothing imports it.

## Depends on

Nothing (first phase).

## Refs

ADR-0009 (package split). PRD §Target architecture, §Phasing.
