# 01 — Frame Source + Frame Sink seams (Offline refactor, behaviour-preserving)

Status: done

## Goal

Factor the two file-bound ends of `pipeline.run()` into a **`FrameSource`** Protocol (where
frames come from) and a **`FrameSink`** Protocol (where annotated frames go), mirroring the
`Detector` seam (ADR-0009). Reproduce today's Offline behaviour **byte-for-byte** with
`FileSource` + `VideoFileSink`. Pure structural move — no Live code yet, no observable change.

## Decisions (from grilling session, ADR-0010)

- **`FrameSource` is a `Protocol`** — iterates frames and exposes `info: sv.VideoInfo`
  (resolution, fps, `total_frames`) so the loop can size annotators / set `ByteTrack`
  `frame_rate` / set the `tqdm` total without knowing the source kind. Add a `release()`.
- **`FrameSink` is a `Protocol`** — `show(frame: np.ndarray) -> bool` (false ⇒ stop) + a
  `close()`. `VideoFileSink` wraps `sv.VideoSink` and **always returns true** (runs to source
  exhaustion). Termination unifies: loop ends when the source is exhausted **or** the sink
  returns false.
- **`run()` depends only on the Protocols.** It no longer calls `from_video_path` /
  `get_video_frames_generator` / `VideoSink` directly — those move into `FileSource` /
  `VideoFileSink`.
- The **sidecar stays a separate concern** (a record stream, not a frame sink); keep it as the
  per-frame JSONL write it is today.

## Tasks

- New `object_tracker/io/` (or `sources.py` + `sinks.py` — pick one; keep modules <200 lines):
  - `FrameSource` Protocol + `FrameSink` Protocol (structural typing, like `_ByteTracker`).
  - `FileSource` — builds `sv.VideoInfo.from_video_path`, iterates
    `sv.get_video_frames_generator`, `release()` is a no-op.
  - `VideoFileSink` — opens `sv.VideoSink` (lazy/`__enter__`), `show()` writes the frame and
    returns `True`, `close()` closes the sink.
- `pipeline.py` — `run(detector, source: FrameSource, sink: FrameSink, zoom, track,
  sidecar_path)`: derive `frame_wh` / `fps` from `source.info`; loop over the source with
  `tqdm(total=source.info.total_frames)`; replace `sink.write_frame` with
  `if not sink.show(annotated): break`; tear down source + sink + sidecar in a `finally`.
- `cli.py` — build `FileSource(paths.source)` + `VideoFileSink(paths.output, info)` and pass
  them to `run()`. No flag changes this phase.
- Tests: `tests/test_io.py` — a fake `FrameSource` (yields known frames + a hand-built
  `sv.VideoInfo`) and a recording fake `FrameSink` drive `run()`; assert the loop reads every
  frame, writes every annotated frame, and calls `close()`/`release()` once. Keep existing
  pipeline/cli tests green.

## Acceptance

1. `pipeline.run` imports/uses only `FrameSource` + `FrameSink`; no direct `VideoSink` /
   `from_video_path` / `get_video_frames_generator` in `pipeline.py`.
2. Offline smoke run (`--classes 14 --no-slice` on the test clip) is **byte-identical**
   annotated video + sidecar to pre-refactor.
3. A fake non-file `FrameSource`/`FrameSink` drives `run()` in a test (proves the seam) without
   touching disk.
4. `uv run pytest` green with no assertion changes beyond moved import paths.

## Depends on

Nothing (first phase).

## Refs

ADR-0010 (the seams), ADR-0009 (Detector-seam precedent). PRD §Target architecture.
