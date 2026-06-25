# General object detection: no bird default; the project is class-agnostic

The detector was always class-agnostic in code (any COCO class via `--classes`, all
classes on custom weights), but the project was *framed* as a bird detector — the
default class, the naming, and the docs all assumed birds. We are removing the bird
framing: the project is now a general object detection + tracking pipeline, and birds
are demoted to one example. Small-object support (sliced inference, recall-first conf)
becomes a *feature*, not the project's identity.

## What changes

- **No silent bird default.** Stock COCO weights now keep **all** classes by default,
  same as custom weights. The class-14 fallback in `_resolve_classes` is removed. Bird
  detection is now an explicit `--classes 14`, not the out-of-the-box behaviour.
- **Identity / docs reframed.** Problem statement, README, and the glossary describe
  detecting and tracking *any* object; `Detector` / `Detector Backend` become the headline
  concepts (the model is swappable — YOLO today, DETR/RF-DETR candidates later — see
  ADR-0009).

## Considered options

- **Keep bird as the stock default** (status quo) — rejected: a tool we now call a general
  detector silently filtering to one class is exactly the least-astonishing-default trap.
- **Couple the default conf to whether `--classes` is given** (0.15 when targeted, higher
  when all-classes) — rejected: a default that silently changes based on another flag can't
  be shown as one number in `--help` and surprises users.

## Consequences

- **Behaviour change.** `detect --source clip.mp4` (no `--classes`) now detects every class,
  not just birds. Existing bird workflows must pass `--classes 14`.
- **ADR-0004 (recall-first `--conf 0.15`) is kept, scope widened to all classes.** Its
  justification — tracking is the false-positive filter — still holds: `--track` is on by
  default, so the *video* draws confirmed tracks only and visible noise stays bounded. The
  *sidecar* gets noisier on busy scenes (more classes × low conf); that noise remains
  by-design. We deliberately did **not** raise the default conf for general mode.
- Birds remain a first-class *use case* (the canonical small-object demo), just not a
  hard-coded default.
