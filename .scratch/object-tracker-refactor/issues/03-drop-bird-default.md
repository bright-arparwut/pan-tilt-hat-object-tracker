# 03 — Drop the bird default (general by default)

Status: ready-for-agent

## Goal

Make general detection the out-of-the-box behaviour: stock COCO weights keep **all** classes,
same as custom weights. Bird detection becomes an explicit `--classes 14`. This is the one
phase that changes observable default behaviour. Record ADR-0008.

## Decisions (from grilling session)

- **No silent class-14 fallback** (ADR-0008). `_resolve_classes`: explicit `--classes` still
  wins; otherwise **keep all classes** regardless of stock vs custom weights.
- **Recall-first `--conf 0.15` kept, scope widened to all classes** (ADR-0004 amended). Do
  **not** raise the default conf and do **not** couple it to `--classes` — both were
  considered and rejected (least-astonishment).

## Tasks

- `cli.py` `_resolve_classes`: drop the `weights_is_default → DEFAULT_CLASS_IDS` branch;
  return `tuple(args.classes)` if given else `None` (all classes). Remove the now-unused
  `weights_is_default` plumbing from `main` if nothing else needs it.
- `config.py`: remove `DEFAULT_CLASS_IDS`; keep `COCO_BIRD_CLASS_ID = 14` only if referenced
  (e.g. tests/docs as the bird example) — otherwise delete it.
- `cli.py` `--classes` help text: "Class ids to keep (default: all classes; e.g. `14` for
  COCO bird)".
- `main` startup print: `classes=None` now means all — make sure the line reads sensibly
  (e.g. `classes=all`).
- Tests: flip `test_resolve_classes_defaults_to_birds_on_stock_weights` →
  `test_resolve_classes_defaults_to_all_classes_on_stock_weights` (asserts `None`). Keep
  `explicit_classes` and `custom_weights_keep_all` tests. Add a test that `--classes 14`
  reproduces bird-only.

## Acceptance

1. `track --source clip.mp4` (no `--classes`, stock weights) detects all classes; sidecar
   shows non-bird classes present in the clip.
2. `--classes 14` reproduces the old bird-only output byte-for-byte.
3. Startup log and `--help` reflect the new default with no bird-default wording.
4. `uv run pytest` green with the flipped/added class tests.

## Depends on

01 (package split). Independent of 02, but sequence after it to keep diffs small.

## Refs

ADR-0008 (no bird default), ADR-0004 (recall-first, scope widened). PRD §CLI surface,
§Acceptance #3.
