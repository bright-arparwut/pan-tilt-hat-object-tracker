# 01 — Project scaffolding with uv

Status: done (implemented in d75e61c on feat/bird-detection-loop)

## Goal

Stand up the project skeleton managed by `uv` so the detection script has a reproducible
environment and a console entry point.

## Tasks

- `uv init`; author `pyproject.toml` with deps: `ultralytics`, `supervision`,
  `opencv-python`, `numpy`, `tqdm`. Python ≥ 3.10.
- Commit `uv.lock`.
- Define a console script entry point `detect-birds` → the script's `main()`.
- Repo layout: single script module (e.g. `detect_birds.py`) with detection logic in
  importable top-level functions (per ADR-0001, the loop must be importable later).
- README: install + run instructions (`uv run detect-birds --source ...`).

## Acceptance

- `uv run detect-birds --help` prints the CLI surface (flags per PRD).
- `uv.lock` is committed and `uv sync` reproduces the env.

## Refs

PRD §Tooling, §CLI surface.
