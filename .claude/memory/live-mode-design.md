---
name: live-mode-design
description: "Design decisions for Live (camera/stream) mode, settled in a grilling session"
metadata: 
  node_type: memory
  type: project
  originSessionId: 1b485e4b-c8fb-424d-be61-faf05820ceff
---

Live (camera/stream) mode was designed in a grill-with-docs session on 2026-06-26 and
recorded in `docs/adr/0010-live-mode-camera-stream-ingestion.md` + `CONTEXT.md`. **Implemented
2026-06-26** on branch `feat/live-cam` (commit `b4891f9`): the six phased issues in
`.scratch/live-mode/` are all `done`. New modules `object_tracker/sources.py`
(FrameSource/FileSource/CameraSource/classify_source) + `sinks.py`
(FrameSink/VideoFileSink/WindowSink/CompositeSink); `pipeline.run` now depends only on those
seams; `cli.py` infers mode from `--source` with tri-state `--slice/--track/--zoom`. 105 tests
green, ruff+pyright clean. Not yet committed to `main` / no PR opened as of that date.

**Settled decisions:**
- **Live preview window** (cv2.imshow) is the primary output; recording optional.
- **Vocabulary is "Live" vs "Offline"**, not "Realtime" (we don't guarantee a latency bound).
- **Process every frame** sequentially (no drop-to-latest / background reader); accept lag or
  driver-dropped frames. Frame index = received-frame counter, not wall-clock.
- **Mode inferred from `--source`**: all-digits → camera index; URL scheme → stream; else → file.
- **Frame Source + Frame Sink Protocol seams** (mirror the Detector seam, ADR-0009); one `run()`.
- **Live defaults are leanest:** slicing off, `--track` off, `--zoom` off; window-only
  (`--sidecar` / `--record` opt-in). Offline defaults unchanged.
- **conf stays 0.15 in both modes**; Live is noisy by default (no tracking filter) → user passes
  `--conf`. Surfaced in CLI help.

**Why:** see ADR-0010 for the trade-offs. Related: [[slicing-currently-broken]].

**How to apply:** When implementing, follow ADR-0010; keep the Offline path behaviour-preserving.
