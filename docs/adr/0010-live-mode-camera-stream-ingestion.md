# Live mode: camera/stream ingestion behind Frame Source + Frame Sink seams

Both prior PRDs listed "live/real-time ingestion" as explicitly out of scope
(`.scratch/*/PRD.md`). We now add it. A [Live Source] — a camera index or stream URL — feeds
the existing [Detection Loop], which shows annotated frames in an on-screen [Live Preview].
To keep the shared `detect → track → annotate → zoom` core untouched, we factor the loop's
two file-bound ends into seams — a **Frame Source** and a **Frame Sink** Protocol — mirroring
the [Detector] seam of ADR-0009. The mode is **inferred from the source**, not a flag: an
integer or URL is Live, a path is Offline.

We call it **Live**, not **Realtime** — see the throughput decision below; we deliberately do
*not* guarantee a latency bound, so "realtime" would overpromise.

## The seams (the load-bearing decision)

- **`FrameSource` is a `Protocol`** — it yields frames and exposes `resolution_wh`, `fps`, and
  a `total` (None when unbounded). `FileSource` wraps today's `sv.VideoInfo` +
  `get_video_frames_generator`; `CameraSource` wraps `cv2.VideoCapture`. The loop never
  branches on which it got.
- **`FrameSink` is a `Protocol`** — `show(frame) -> bool`, where a false return stops the loop.
  `VideoFileSink` wraps `sv.VideoSink` and always returns true (runs to source exhaustion);
  `WindowSink` calls `cv2.imshow` + `cv2.waitKey(1)` and returns false on `q`/window-close.
  Termination is thus unified: the loop ends when the source is exhausted **or** the sink says
  stop. `--record` is just a composite sink (window **and** file).
- **`run()` depends only on the Protocols.** The Offline path becomes `FileSource +
  VideoFileSink`; Live is `CameraSource + WindowSink` (+ optional file/sidecar).

## Source overloading (mode inference)

`--source` stays a single argument and the mode falls out of its shape:

- all-digits (`--source 0`) → camera **index** (Live)
- a URL scheme — `rtsp:// http:// https:// udp:// tcp://` (`--source rtsp://…`) → **stream** (Live)
- anything else (`--source clip.mp4`) → **file path**, must `exist()` (Offline)

`cv2.VideoCapture` accepts all three through one call, so stream-URL support comes for free
alongside the local webcam.

## Throughput: process every frame, accept lag

On a [Live Source] the camera produces frames in real time regardless of the loop's pace. We
**process frames sequentially in the main loop** (no background reader, no drop-to-latest) and
number them `0,1,2,…` as received. The honest consequence: if detection can't keep up, the OS
driver buffer drops frames before we see them, **or** the preview drifts behind wall-clock —
which one is up to AVFoundation, not us. Hence the frame index counts *received* frames, not
time; a persisted Live sidecar therefore also carries a capture timestamp.

To make "keep up" achievable, **Live mode defaults to the leanest config**: whole-frame
inference (slicing **off**), tracking **off**, zoom **off** — plain detection boxes. Offline
defaults are unchanged (slicing/track/zoom on). All are overridable per run.

## Considered options

- **Drop-to-latest** (background reader holds newest frame, skip the backlog) — rejected for
  v1: it keeps latency bounded but yields a non-contiguous sidecar and needs a reader thread.
  Reconsider if the lag proves unacceptable in practice.
- **A parallel `run_live()`** duplicating the loop — rejected: it duplicates the
  detect/track/annotate orchestration, inviting drift between the two paths. The seams cost a
  little up-front refactor of the working Offline path but keep one loop.
- **An explicit `--live` flag / a `track-live` subcommand** — rejected: source-type inference
  is enough and matches the ultralytics/OpenCV `source=0` convention; a flag/subcommand adds
  surface for no gain.
- **Naming it "Realtime"** — rejected: we don't enforce a latency bound, so the glossary would
  lie. "Live" describes the source, not a promise.

## Consequences

- **Noisy Live view by default.** `conf=0.15` is recall-first *because tracking is the FP
  filter* (ADR-0004), but Live defaults tracking off — so at 0.15 the window shows many
  low-confidence boxes. We keep one `conf` default across modes (no mode-specific magic); the
  fix is a manual `--conf 0.3`. Surfaced in the CLI help.
- **`--record` time-compression.** A recorded Live video is written at the source's nominal
  fps with no per-frame PTS; if processing runs slower than real time, playback is
  time-compressed. Acceptable for a preview-first feature; documented, not fixed.
- **Camera `VideoInfo` is derived, not read from a file.** Width/height come from
  `CAP_PROP_FRAME_*`; `fps` falls back to a nominal default when the device reports 0 (it feeds
  `sv.ByteTrack`'s `frame_rate` and annotator scaling, both frame-count based). `total` is
  None, so the progress bar is an open-ended counter.
- **Clean shutdown.** `q`, window-close, EOF, and `Ctrl-C` all release the capture, destroy the
  window, and flush/close any sidecar or recorder via a single `finally`.
- **Related but separate: slicing is currently broken.** This reinforces "slicing off in Live"
  but the bug also breaks the Offline default path; tracked as its own issue, not fixed here.
