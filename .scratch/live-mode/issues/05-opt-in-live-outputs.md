# 05 — Opt-in Live outputs: `--sidecar` (with capture ts) + `--record`

Status: done

## Goal

Let a Live run optionally persist what it sees: `--sidecar` appends the JSONL detections
stream (with a capture timestamp, since the frame index isn't a clock on a Live Source), and
`--record PATH` also writes an annotated `.mp4` alongside the window via a `CompositeSink`.
Both are **off by default** in Live; Offline output is unchanged.

## Decisions (from grilling session, ADR-0010)

- **Window-only is the Live default.** `--sidecar` and `--record` are explicit opt-ins in Live.
  In Offline both remain on/derived as today (no regression).
- **Live sidecar carries `ts`.** Because the frame index counts *received* frames (not
  wall-clock), each Live record is `{"frame": idx, "ts": <epoch_seconds>, "detections": [...]}`.
  Capture the ts as close to frame read as practical. **Offline schema is unchanged** (no `ts`).
- **`--record` = CompositeSink(WindowSink, VideoFileSink).** The recorded file is written at the
  source's nominal/derived fps with no per-frame PTS — if processing runs slower than real time
  the playback is time-compressed. Accepted + documented (ADR-0010 §Consequences), not fixed.

## Tasks

- `cli.py` — add `--record PATH` (default None); in Live, wire `--sidecar`/`--record` into the
  sink + sidecar-path passed to `run()`:
  - no flags → `WindowSink`, `sidecar_path=None`;
  - `--record P` → `CompositeSink([WindowSink, VideoFileSink(P, info)])`;
  - `--sidecar P` (or default Live path when bare) → pass the path so `run()` opens it.
- `pipeline.run` — when the source is Live, include `ts` in the per-frame JSONL object; keep the
  Offline write byte-identical. Consider a tiny `frame_record(idx, records, ts=None)` helper so
  the schema branch lives in one place (sidecar.py).
- Offline `--record` is a no-op/!error? — keep it Live-only for now (Offline already writes the
  annotated video); reject `--record` with a clear message in Offline, or ignore. Pick one and
  test it.
- Tests: Live `--sidecar` JSONL rows include a numeric `ts` and the existing detection fields;
  Offline sidecar has **no** `ts` (byte-for-byte unchanged); `--record` builds a `CompositeSink`
  (mocked `VideoFileSink`) and writes every frame; the Offline-`--record` decision is asserted.

## Acceptance

1. Live `--sidecar` appends `{"frame", "ts", "detections"}` rows; Offline sidecar is unchanged
   (no `ts`, byte-for-byte).
2. Live `--record PATH` writes an annotated `.mp4` and still shows the window (CompositeSink,
   mocked in tests); without it nothing is written.
3. The Offline-`--record` behaviour (reject or ignore) is defined and tested.
4. `uv run pytest` green.

## Depends on

03 (`CompositeSink` / `VideoFileSink`), 04 (Live wiring).

## Refs

ADR-0010 (§Throughput — received-frame index, §Consequences — record time-compression).
PRD §CLI surface, §Acceptance 6.
