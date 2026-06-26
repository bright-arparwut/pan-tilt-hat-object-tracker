# 06 — Docs sync: README, CLI help, cross-references

Status: done

## Goal

Bring the human-facing docs in line with Live mode. The domain docs are **already written**
(ADR-0010 + the *Sources, sinks & modes* cluster in `CONTEXT.md`, done during the grilling
session); this phase syncs the README, the CLI docstring/`--help`, and the stale
"out-of-scope" notes in the prior PRDs.

## Decisions (from grilling session, ADR-0010)

- **Don't restate the design.** Link to ADR-0010 / `CONTEXT.md`; the README shows *usage*, not
  rationale (matches the existing README style).
- **Live vs Offline** is the framing everywhere — never "realtime" in prose except to note the
  deliberate naming choice.

## Tasks

- `README.md` — add a short **Live mode** usage block: `uv run track --source 0`,
  `--source rtsp://…`, the noisy-without-`--track` `--conf` hint, and `--sidecar` / `--record`
  opt-ins. Note `q` / window-close to quit. Link ADR-0010.
- `cli.py` module docstring — extend the one-liner to mention Live (`--source 0`) alongside the
  Offline file path; ensure `--help` text from 04/05 reads cleanly.
- Prior PRDs — add a one-line note to `.scratch/object-tracker-refactor/PRD.md` §Scope and
  `.scratch/bird-detection-loop/PRD.md` §Future that live ingestion is **now delivered** by
  `.scratch/live-mode/` (ADR-0010).
- Sanity-check `CONTEXT.md` terms resolve (no dangling `[Live Source]` / `[Frame Sink]` links)
  and ADR-0010 cross-refs are correct.
- Update `.scratch/live-mode/issues/*` `Status:` lines to `done` as phases land (housekeeping).

## Acceptance

1. README documents Live usage (camera + stream + opt-in outputs + quit keys) and links
   ADR-0010; no "realtime" promise in prose.
2. `track --help` and the `cli.py` docstring mention Live `--source 0` / streams.
3. Prior PRDs point forward to `live-mode` for the previously-deferred live ingestion.
4. No dangling glossary cross-references; `uv run pytest` still green (docs-only, but run it).

## Depends on

04, 05 (so help/usage reflect the shipped flags).

## Refs

ADR-0010, `CONTEXT.md` (§Sources, sinks & modes). PRD §Acceptance 8.
