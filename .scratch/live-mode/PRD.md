# PRD — Live mode (camera / stream ingestion + on-screen preview)

> Adds the **Live/real-time ingestion** that both prior PRDs explicitly deferred
> (`.scratch/object-tracker-refactor/PRD.md` §Scope, `.scratch/bird-detection-loop/PRD.md`
> §Future). Design settled in a grill-with-docs session; recorded in **ADR-0010** and the
> *Sources, sinks & modes* cluster of `CONTEXT.md`. This PRD phases the build.

## Problem

The pipeline is offline-only: `run()` is bound to a file at both ends —
`sv.VideoInfo.from_video_path` + `get_video_frames_generator` (input) and `sv.VideoSink`
(output), with a `tqdm` total that assumes a finite clip. We want to point the same
detect → track → annotate loop at a **live camera (or stream)** and **watch annotated
detections in a window**, without forking the loop.

## Scope

**In scope (this deliverable):**
- A **Live Source** (camera index or stream URL) and an on-screen **Live Preview** window,
  selected by `--source` *type* (no new mode flag) — see ADR-0010.
- Factor the loop's two file-bound ends into a **Frame Source** and a **Frame Sink** Protocol
  seam (mirroring the `Detector` seam, ADR-0009); refactor Offline onto them
  behaviour-preservingly.
- **Process every frame** sequentially (no drop-to-latest); leanest Live defaults
  (slicing/track/zoom off, window-only); opt-in `--sidecar` / `--record`.

**Out of scope (design for, don't build):**
- **Drop-to-latest / background-reader** frame skipping. We accept lag; revisit only if it
  proves unusable (ADR-0010 §Considered options).
- **Fixing the broken slicer.** Slicing is currently broken; tracked separately. Live never
  depends on it, so this work is unblocked.
- Recording with preserved per-frame PTS (a `--record` Live video is nominal-fps, possibly
  time-compressed — ADR-0010 §Consequences). Streaming *out*, multi-camera, re-acquisition.

## Key decisions (see ADR-0010)

- **Live vs Offline**, not "Realtime" — we process every frame and do **not** guarantee a
  latency bound, so the preview may lag / the OS driver may drop frames. Frame index counts
  *received* frames, not wall-clock time.
- **Mode inferred from `--source`:** all-digits → camera index; URL scheme
  (`rtsp:// http:// https:// udp:// tcp://`) → stream; else → file path (`exist()`-checked).
  `cv2.VideoCapture` accepts all three, so stream URLs come for free.
- **`FrameSource` + `FrameSink` Protocols.** `run()` depends only on them. Offline =
  `FileSource + VideoFileSink`; Live = `CameraSource + WindowSink` (+ optional file). Sink
  contract `show(frame) -> bool` (false = stop) unifies termination (EOF **or** `q`).
- **Live defaults are leanest:** slicing off, `--track` off, `--zoom` off, window-only.
  Mode-sensitive toggles become tri-state (unset → mode default; explicit flag always wins).
  Offline defaults unchanged.
- **conf stays 0.15 both modes** (no mode-specific magic). Live is noisy by default (no
  tracking filter, ADR-0004) → surface a `--conf` hint in help.

## Target architecture

The shared core is untouched; only the source/sink ends change:

```
            ┌─ FileSource  (sv.VideoInfo.from_video_path + frames gen, total=N)   ── Offline
 --source ──┤
            └─ CameraSource(cv2.VideoCapture; VideoInfo derived, fps fallback,    ── Live
                            total=None)
                 │
                 ▼   for frame in source:                 (tqdm total = info.total_frames | None)
        detector.detect(frame) ──▶ sv.Detections          (Live default: --no-slice)
                 │
         optional ByteTrack + zoom (Live default: off)
                 │  annotated frame
                 ▼
            sink.show(frame) -> keep_going                 (false ⇒ stop)
            ┌─ VideoFileSink (sv.VideoSink, always true)                          ── Offline
   sink  ──┤─ WindowSink     (cv2.imshow + waitKey; false on q / window-close)    ── Live
            └─ CompositeSink  (Window + VideoFile, for --record)
                 │  (sidecar is a separate optional record stream; Live adds a capture ts)
```

`run(detector, source: FrameSource, sink: FrameSink, ...)` builds annotators / ByteTrack from
`source.info` (resolution + `round(fps)`), loops, and tears down capture + sink + sidecar in a
single `finally` (covers `q`, window-close, EOF, `Ctrl-C`).

## CLI surface

`--source` is unchanged in spelling; its *value* now selects the mode. New/changed:

| Flag | Behaviour |
| --- | --- |
| `--source 0` / `rtsp://…` | **New** — Live Source (camera index / stream). Skips the `exist()` + `from_video_path` file checks. |
| `--source clip.mp4` | Unchanged — Offline. |
| `--slice` / `--track` / `--zoom` | Defaults become **mode-sensitive** (Offline on, Live off); an explicit flag always wins. |
| `--sidecar` | **New semantics in Live** — opt-in; Live records carry a capture `ts`. Offline writes it as today. |
| `--record PATH` | **New** — in Live, also write an annotated `.mp4` (CompositeSink). |
| all others (`--weights`, `--device`, `--conf`, `--classes`, `--slice-wh`, …) | Unchanged. |

## Acceptance criteria

1. **Seams (ADR-0010).** `pipeline.run` depends only on `FrameSource` + `FrameSink`; Offline
   is `FileSource + VideoFileSink` and produces **byte-identical** annotated video + sidecar to
   pre-refactor on a fixed clip/seed.
2. **Live runs.** `track --source 0` opens the default camera and shows a live annotated window
   of plain detection boxes (slicing/track/zoom off); `q` or closing the window ends the run
   cleanly (capture released, window destroyed).
3. **Stream parity.** `--source rtsp://…` follows the same Live path (no camera-only code).
4. **Mode inference.** Source classification (digits / URL scheme / path) is unit-tested;
   file-only validation (`exist()`, `from_video_path`) runs only for file sources.
5. **Live defaults + override.** With no flags, Live has slicing/track/zoom off and writes no
   files; each can be re-enabled explicitly (`--track`, `--zoom`, `--slice`), and Offline
   defaults are unchanged.
6. **Opt-in outputs.** `--sidecar` in Live appends JSONL with a capture `ts` per frame;
   `--record PATH` writes an annotated `.mp4` alongside the window. Offline sidecar schema is
   byte-for-byte unchanged (no `ts`).
7. **Tests green.** `uv run pytest` passes; new tests cover the seams, source classification,
   `CameraSource` over a fake `VideoCapture`, `WindowSink`/`CompositeSink` termination, and the
   tri-state default resolution.
8. **Docs synced.** README + CLI docstring/`--help` describe Live mode; ADR-0010 + CONTEXT
   (already written) referenced; prior PRDs' "live out of scope" notes marked as delivered here.

## Phasing

See `issues/` — six independently-green phases (each keeps the suite green; only `04`–`06`
add observable Live behaviour):
`01` Frame Source + Sink seams (Offline refactor) → `02` Live Source (camera/stream) →
`03` Live Preview sink + termination → `04` wire Live end-to-end (mode inference + Live
defaults) → `05` opt-in Live outputs (`--sidecar` ts + `--record`) → `06` docs sync.
