# 04 — Rename & de-brand: detect-birds → track, project → object-tracker

Status: done (implemented in ef2674d; GitHub repo/dir rename still pending — out-of-band user action)

## Goal

Complete the clean-break rename: console script `detect-birds → track`, project
`yolo-bytetrack-sot → object-tracker`, and strip remaining bird framing from user-facing
strings. The import package is already `object_tracker` (from 01). No alias, no shim.

## Decisions (from grilling session)

- **Full rename, clean break.** Backend-agnostic name `object-tracker` (the detector can be
  YOLO, DETR, RF-DETR — the name shouldn't lie). Console verb is `track`.
- **No back-compat alias.** Pre-1.0 personal branch; muscle-memory `detect-birds` breaking is
  acceptable (ADR-0009).
- **Repo rename** (`yolo-byteTrack-sot` → `object-tracker`) is a GitHub/local-dir action done
  by the user, out of band — note it, don't script it here.

## Tasks

- `pyproject.toml`: `name = "object-tracker"`; `[project.scripts] track = "object_tracker.cli:main"`;
  update `description` to the general framing; keep deps/pins (supervision `<0.30` per
  ADR-0006).
- `cli.py`: `argparse` `prog="track"`; module docstring de-birded (describe general
  detection+tracking; birds as an example); update the `main` startup print prefix/wording.
- README: rewrite headline + examples around general detection (see issue 05 for the full
  docs pass; at minimum the run commands must use `track` and not imply a bird default).
- Grep for residual "bird" in code/strings (`rg -i bird object_tracker tests`) and resolve
  each: keep only legitimate *example* mentions and `COCO_BIRD_CLASS_ID`/`--classes 14`
  references.
- `uv.lock`/`uv sync`: regenerate so the `track` console script is installed; confirm
  `uv run track --help` works and `uv run detect-birds` is gone.

## Acceptance

1. `uv run track --help` works; `prog` is `track`; help carries no bird-default wording.
2. `uv run detect-birds` no longer resolves; no `detect_birds` module anywhere.
3. `pyproject` name is `object-tracker`, entry point `object_tracker.cli:main`, wheel ships
   the package.
4. `rg -i bird object_tracker tests` returns only intentional example/`--classes 14` hits.
5. `uv run pytest` green.

## Depends on

01 (package), 03 (default semantics referenced in help/README). Best done after 02–03.

## Refs

ADR-0008, ADR-0009. PRD §CLI surface (after rename), §Acceptance #5.
