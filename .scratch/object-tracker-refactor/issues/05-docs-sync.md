# 05 — Docs sync & supersede

Status: done (implemented in ef2674d on feat/object-tracker-refactor)

## Goal

Land the documentation pass so the repo's docs describe the general `object-tracker`
pipeline, and mark the bird-era tracking docs superseded. Most design docs are already
written during the grilling session; this phase finalises README and verifies cross-refs
against the shipped code.

## Already written (grill-with-docs session)

- `CONTEXT.md` — de-birded; added `Detector`, `Detector Backend`, `Sliced Detector`;
  `Annotated Video`/`Sliced Inference` reworded.
- `docs/adr/0008-general-detection-no-bird-default.md`.
- `docs/adr/0009-package-split-and-detector-seam.md`.
- `.scratch/object-tracker-refactor/PRD.md`.
- `.scratch/bird-detection-loop/PRD.md` — superseded banner added.

## Tasks

- **README**: rewrite around general detection + tracking. Title/intro de-birded; examples
  use `track`; show `--classes 14` as the "birds" example and a non-bird example (e.g.
  `--classes 0 2` for person+car). Keep the slicing/recall-first/cost notes (still true).
- **Verify cross-refs** once 01–04 land: module paths in ADR-0009 and the PRD match the
  actual `object_tracker/` tree; CLI table matches `build_parser`; `Detector`/`SlicedDetector`
  names match `detection/`.
- **Old issue notes**: add a one-line "superseded by `.scratch/object-tracker-refactor/`"
  pointer at the top of `.scratch/bird-detection-loop/issues/` index or PRD (PRD banner
  already covers this — only touch issues if they're cited elsewhere).
- **CLAUDE.md**: no change expected (conventions unchanged); confirm the issue-tracker/domain
  doc pointers still hold.

## Acceptance

1. README describes general detection+tracking; every command uses `track`; no command
   implies a bird default; birds appear only as an example.
2. ADR-0009 and the PRD's module tree match the real package; CLI table matches `--help`.
3. `.scratch/bird-detection-loop/PRD.md` shows the superseded banner pointing here.
4. `rg -i bird README.md docs CONTEXT.md` returns only intentional example mentions.

## Depends on

01–04 (docs must match shipped code).

## Refs

ADR-0008, ADR-0009, CONTEXT.md, PRD. Conventions: `docs/agents/issue-tracker.md`,
`docs/agents/domain.md`.
