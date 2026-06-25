# PRD — object-tracker (general object detection + tracking in video)

> Supersedes `.scratch/bird-detection-loop/PRD.md`. That PRD delivered the bird-framed
> detection+tracking loop; this one reframes the same engine as a **general** object
> detection + tracking pipeline and splits the monolith into modules. No new detection
> capability beyond the reframe — see "Scope".

## Problem

We have a working detection + tracking loop, but it is *framed* as a bird detector: the
default class, the naming (`detect_birds` / `detect-birds` / project `yolo-bytetrack-sot`),
and the docs all assume birds — even though the engine has always been class-agnostic. We
want a **general object detection + tracking pipeline**: detect and track *any* object in
video, any class, any weights; with a **swappable detector backend** (YOLO today; DETR /
RF-DETR candidates later) and small-object support (sliced inference) as a *feature*, not the
identity. Birds become one example.

## Scope

**In scope (this deliverable — a refactor, mostly behaviour-preserving):**
- Split `detect_birds.py` into an `object_tracker/` package, one module per pipeline stage
  (ADR-0009).
- Promote the detector to a backend-agnostic `Detector` seam; make slicing a `SlicedDetector`
  decorator over any backend (ADR-0009). Implement the **YOLO backend only**.
- Drop the bird default: stock weights keep all classes; reframe naming and docs (ADR-0008).
- Rename: console `detect-birds → track`, project `yolo-bytetrack-sot → object-tracker`,
  package `object_tracker`. Clean break — no alias, no shim.

**Out of scope (future phases — design for, don't build):**
- A second `Detector Backend` (DETR / RF-DETR). The seam is built; the backend is not.
- Custom-class training/management UX beyond passing `--classes` / custom `--weights`.
- Live/real-time ingestion, model training, and dedicated single-object re-acquisition
  (carried over from the prior PRD's "Future").

## Key decisions (see `docs/adr/`)

- **ADR-0008** — General object detection: **no bird default**. Stock weights keep all
  classes; bird is now explicit `--classes 14`. Recall-first `--conf 0.15` (ADR-0004) is
  kept, scope widened to all classes; default conf is **not** raised and **not** coupled to
  `--classes`.
- **ADR-0009** — Split into an `object_tracker/` package behind a backend-agnostic `Detector`
  Protocol. **Slicing is a `SlicedDetector` decorator** over any Detector (revises ADR-0003's
  slicing-on-the-YOLO-path assumption) — a future backend gets sliced inference for free.
  Reverses the prior PRD's "single Python script" constraint. No back-compat shim.
- **Carried, unchanged:** ADR-0001 (standalone detections + sidecar handoff), ADR-0002
  (slicing as a runtime toggle, resolution-agnostic), ADR-0003 (sliced inference via
  supervision's `InferenceSlicer`, not obss/sahi), ADR-0004 (recall-first; tracker is the FP
  filter), ADR-0005 (confidence-mode zoom under `--no-track`), ADR-0006 (in-loop
  `sv.ByteTrack`), ADR-0007 (identity-mode zoom).

## Target architecture

```
object_tracker/
  config.py     device.py
  detection/base.py  detection/yolo.py        # Detector Protocol + YoloDetector + SlicedDetector
  tracking.py   zoom.py   sidecar.py
  pipeline.py   cli.py
```

Data flow is unchanged from the prior PRD; the only structural change is the detector seam:

```
video file ─▶ frame loop
                 │
                 ▼
        detector.detect(frame) ──▶ sv.Detections
          detector = build_detector(cfg):
            base = YoloDetector(weights, conf, classes, device)
            det  = SlicedDetector(base, slice_wh, overlap) if --slice else base
                 │
        ┌────────┴─────────┐
        ▼                  ▼
   --track: sv.ByteTrack   sidecar (JSONL, raw rows + nullable track_id)
   annotate confirmed      annotate raw boxes (--no-track)
   + identity zoom         + confidence zoom (--no-track)
        ▼
   sv.VideoSink.write_frame
```

Both detector branches (and any future backend) return `sv.Detections`, so everything
downstream is identical regardless of backend or slicing — the ADR-0002/0003 invariant.

## CLI surface (after rename)

Console script: **`track`** (was `detect-birds`). Flags are unchanged except the `--classes`
default semantics (ADR-0008):

| Flag | Default | Change |
| --- | --- | --- |
| `--classes` | **all classes** (was: bird/14 on stock weights) | **Changed** (ADR-0008) |
| all other flags (`--source`, `--weights`, `--device`, `--conf`, `--slice`, `--slice-wh`, `--overlap-ratio`, `--overlap-filter`, `--thread-workers`, `--zoom*`, `--track*`) | as today | Unchanged |

To reproduce the old default: `track --source clip.mp4 --classes 14`.

## Acceptance criteria

1. **Package & seam (ADR-0009).** Code lives in `object_tracker/` (stage modules per the
   tree above); `from object_tracker.detection import Detector, YoloDetector, SlicedDetector`
   resolves; the pipeline imports the `Detector` Protocol, never YOLO directly.
2. **Slicing decorator.** `SlicedDetector` wraps a `Detector` and produces **byte-identical**
   detections to the old `make_detector` sliced path on the same clip/seed; `--no-slice` uses
   the bare backend.
3. **No bird default (ADR-0008).** `track --source clip.mp4` (no `--classes`) detects all
   classes on stock weights; `--classes 14` reproduces bird-only. The
   `_resolve_classes`-defaults-to-bird test is flipped to assert all-classes.
4. **Behaviour preserved otherwise.** With `--classes 14`, annotated video + sidecar +
   tracking + zoom (both modes) are byte-for-byte the pre-refactor outputs.
5. **Rename complete.** Console script is `track`; `pyproject` name is `object-tracker`,
   wheel ships the package, entry point `object_tracker.cli:main`. No `detect_birds` module,
   no `detect-birds` alias. README and module docstrings carry no bird framing (birds
   referenced only as an example).
6. **Tests green & rewired.** Suite imports from `object_tracker.*`, split to mirror the
   modules; all prior assertions hold except the deliberately-changed bird-default test.
7. **Docs synced.** `CONTEXT.md` de-birded + `Detector`/`Detector Backend`/`Sliced Detector`
   added; ADR-0008/0009 recorded; old `.scratch/bird-detection-loop/` PRD marked superseded.

## Phasing

See `issues/` — five independently-green phases:
`01` package split → `02` detector seam → `03` drop bird default → `04` rename/de-brand →
`05` docs sync. Each phase keeps the suite green; only `03` and `04` change observable
behaviour/contract.
