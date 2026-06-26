# 04 — Wire Live mode end-to-end: mode inference + mode-sensitive defaults

Status: done

## Goal

Make `track --source 0` (or a stream URL) actually run: select `CameraSource` + `WindowSink`
from the source type, skip the file-only validation for Live sources, and flip the
**mode-sensitive defaults** (slicing / track / zoom **off** in Live). End state: a live,
window-only preview of plain detection boxes.

## Decisions (from grilling session, ADR-0010)

- **Mode from `classify_source` (02), not a flag.** File spec → `FileSource` + `VideoFileSink`
  (today's path, unchanged). Camera/stream spec → `CameraSource` + `WindowSink`.
- **File-only validation is gated.** `source.exists()` + `sv.VideoInfo.from_video_path` run
  **only** for file sources; a camera/stream skips them (the `CameraSource` open-failure error
  from 02 is the Live equivalent).
- **Mode-sensitive toggles via tri-state.** `--slice` / `--track` / `--zoom` become
  `BooleanOptionalAction` with `default=None`; after parsing resolve `None → (False if live
  else True)`. **An explicit flag always wins** (`--track` re-enables tracking in Live).
- **conf unchanged (0.15 both modes).** Add a one-line `--help`/startup hint that Live is noisy
  without `--track`; suggest `--conf`. No behavioural coupling (ADR-0004 kept).
- The startup `print(...)` line gains the mode (`mode=live|offline`) and, for Live, the
  resolved source label.

## Tasks

- `cli.py`:
  - Replace the unconditional `Path(args.source)` / `exists()` / `from_video_path` block with
    `classify_source(args.source)` and a branch: file → validate + `FileSource` +
    `VideoFileSink`; camera/stream → `CameraSource` (+ `WindowSink`, built in 03).
  - Convert `--slice` / `--track` / `--zoom` to `default=None`; add `resolve_toggles(args,
    is_live)` returning the effective bools; feed `DetectConfig` / `TrackConfig` / `ZoomConfig`.
  - Re-run `validation_error` against the **resolved** values (e.g. `--zoom-track-id` still
    requires the resolved `track`).
  - Update the startup print + `build_parser` help text (mode-sensitive default note, `--conf`
    hint).
- `pipeline.run` call site: pass the chosen `source` + `sink`.
- Tests (`test_cli.py`): `--source 0` selects Live (mocked `CameraSource`/`WindowSink`) and
  skips `exists()`/`from_video_path`; tri-state resolution table (Live unset → off; Offline
  unset → on; explicit flag wins in both); `--zoom-track-id` validation uses resolved `track`;
  Offline path/flags byte-for-byte unchanged.

## Acceptance

1. `track --source 0` runs Live end-to-end (mocked capture/window in tests): `CameraSource` +
   `WindowSink`, no file checks, plain boxes (slice/track/zoom resolved off), nothing written.
2. `track --source clip.mp4` is unchanged (Offline defaults on, file validation runs).
3. Explicit `--track` / `--zoom` / `--slice` override the Live-off defaults; explicit
   `--no-track` etc. override Offline-on defaults.
4. `track --source rtsp://…` takes the same Live path as a camera index.
5. `uv run pytest` green; no real device/network/window in tests.

## Depends on

02 (Live Source + `classify_source`), 03 (`WindowSink`).

## Refs

ADR-0010 (§Source overloading, §Throughput — Live defaults, §Consequences — noisy default).
PRD §CLI surface, §Acceptance 2/4/5.
