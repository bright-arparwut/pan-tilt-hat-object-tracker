# Week 1 — Frame I/O & the loop

**Hours:** 6 · **Where:** Mac · **Milestone:** copy a video frame-by-frame through your own loop

## Why this week

Before any model, you need to be fluent in the thing every later week manipulates: **a video
is a generator of numpy arrays**, and a frame is an `(H, W, 3)` uint8 array in **BGR** order
(not RGB — OpenCV's historical quirk, and the source of a classic "why is everything blue"
bug).

You'll also build the two things that make the rest of the project tractable: **frozen
dataclass config** and a loop whose `finally` releases everything.

## Concepts

By the end you should be able to answer, without looking:

- What are the shape, dtype and channel order of a decoded frame? What happens if you get
  the channel order wrong?
- Why is `sv.VideoInfo` (width, height, fps, total_frames) needed *before* the loop starts,
  rather than derived inside it?
- Why is every config object `@dataclass(frozen=True)`? What bug class does that kill?
- Why does `pipeline.run` wrap its loop in `try/finally` with **nested** `finally` blocks?
  (Hint: what happens to the camera handle if closing the window raises?)

Read: OpenCV `VideoCapture`/`VideoWriter` basics, `supervision`'s `VideoInfo` and
`get_video_frames_generator`, Python's `dataclasses` with `frozen=True`.

## Sessions

**Session 1 (2h) — scaffold.** `uv init`, `pyproject.toml`, `pytest` running. Get
`uv run pytest` to collect and fail cleanly. Then `config.py`: implement `DetectConfig`,
`RunPaths`, `ZoomConfig` (leave the turret ones for month 3). The enums and constants are
given — read their comments, they're teaching material.

**Session 2 (2h) — the source and sink.** `sources.FileSource` and `sinks.VideoFileSink`.
Note the shape of the `FrameSource` Protocol you're given: an `info` attribute, `__iter__`,
`release`. Don't generalise it yet — you only have files. Week 8 is where it earns the
abstraction.

**Session 3 (2h) — the loop.** `pipeline.run`, detector-less: read a frame, hand it straight
to the sink. It should produce a byte-identical copy of the input video. Get the teardown
right — that's the part that's actually hard.

## Files you implement

| File | What |
|---|---|
| `object_tracker/config.py` | `DetectConfig`, `RunPaths`, `ZoomConfig` dataclasses |
| `object_tracker/sources.py` | `FileSource` only |
| `object_tracker/sinks.py` | `VideoFileSink` only |
| `object_tracker/pipeline.py` | `run()`, without the detector branch |

## Tests you're given

`tests/test_io.py::test_file_source_reports_video_info`,
`::test_video_file_sink_writes_every_frame`,
`::test_pipeline_releases_source_even_when_sink_close_raises`

That third one is the contract that matters. Make it pass and you've understood the
teardown.

## Tests you write

- `FileSource` on a missing path — what *should* happen?
- `VideoFileSink` creating a parent directory that doesn't exist
- The loop over a zero-frame video

## Milestone

```bash
uv run pytest tests/test_io.py        # all three green
```

Then prove it end to end:

```bash
uv run python -c "
from pathlib import Path
from types import SimpleNamespace
from object_tracker.sources import FileSource
from object_tracker.sinks import VideoFileSink
from object_tracker.pipeline import run

src = FileSource(Path('../footage/clip.mp4'))
off = SimpleNamespace(enabled=False)   # stand-ins until weeks 6-7 fill the real configs
run(None, src, VideoFileSink(Path('/tmp/copy.mp4'), src.info), off, off)
"
```

`/tmp/copy.mp4` plays and has the same frame count as the input.

Note the two ``off`` stand-ins: this week's ``run`` only ever asks a config whether a feature
is ``enabled``, so anything with that attribute will do. That is a hint about how little the
loop should know.

## ADR to write

**ADR-0001 — The detection loop emits a standalone detections record.** You haven't built
the sidecar yet (week 3), but decide *now* whether detections should be a side output or
embedded in the video, and write down why. Then compare with the root repo's ADR-0001.

## Stuck?

The reference is `../sources.py`, `../sinks.py`, `../pipeline.py` — but read
`.scratch/bird-detection-loop/issues/01-project-scaffolding-uv.md` and
`02-video-io-frame-loop.md` in the root repo first. Those are the original specs for exactly
this week.
