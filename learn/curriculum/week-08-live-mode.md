# Week 8 — Live mode & the source/sink seams

**Hours:** 7 · **Where:** Mac · **Milestone:** `--source 0` live webcam preview

## Why this week

Week 1 gave you a `FrameSource` Protocol with exactly one implementation — which means it
wasn't really an abstraction, it was a class with extra steps. This week a second, genuinely
different implementation arrives and the seam either holds or it doesn't.

A live source breaks three assumptions baked into the offline path: **it never ends**, **it has
no frame count**, and **frames arrive whether or not you're ready**. Generalising under that
pressure — rather than guessing up front — is how good abstractions actually get made.

## Concepts

- **Unbounded sources.** `total_frames=None`. What does `tqdm` do with that? What does your
  progress bar mean now?
- **Unified termination.** The loop must end when the source is exhausted **or** the sink says
  stop. That's why `FrameSink.show()` returns a bool. One `break`, two reasons — and it's why
  closing a window and reaching EOF need no separate handling.
- **Composition.** `CompositeSink` fans one frame to many. Note it does **not** short-circuit:
  if the window says stop, the file sink still records that frame. Work out why before reading
  the docstring.
- **Mode inference, not a flag.** `--source 0` is live; `--source clip.mp4` is offline. No
  `--live` flag exists (ADR-0010). Is that good design or cleverness? Argue it.
- **Tri-state toggles.** `--track` / `--no-track` / unset. Unset means "the mode's default":
  on for offline, off for live. `resolve_toggle` is four lines and encodes a real product
  decision.
- **Live ≠ realtime.** This is the week's most important idea. The project processes every
  frame sequentially and guarantees **no latency bound**. If detection can't keep up you get
  growing lag or driver-dropped frames, and a `--record` file written at nominal fps is
  **time-compressed**. That's why live sidecar rows carry a wall-clock `ts` — the frame index
  counts *received* frames, not time. Realtime means a deadline. This has none.

## Sessions

**Session 1 (2h) — classify and capture.** `classify_source` (pure: digits → camera index,
known scheme → stream URL, else file path — no I/O, fully testable). Then `CameraSource`,
including `_derive_info` and the fps-reports-zero fallback.

**Session 2 (2.5h) — sinks.** `WindowSink` (both quit paths: `q` **and** the window's close
button — test the second, it's the one people forget) and `CompositeSink` (including
closing every child even when one raises, then re-raising the first).

**Session 3 (2.5h) — the CLI.** `resolve_toggle`, `_select_source_sink`, `validation_error`,
`--record`. The mode-sensitive validation is fiddlier than it looks: validate against the
*resolved* toggles, not the raw flags.

## Files you implement

| File | What |
|---|---|
| `object_tracker/sources.py` | `CameraSpec`, `FileSpec`, `classify_source`, `CameraSource` |
| `object_tracker/sinks.py` | `WindowSink`, `CompositeSink` |
| `object_tracker/cli.py` | `resolve_toggle`, `_select_source_sink`, `validation_error`, `--record` |
| `object_tracker/pipeline.py` | the `is_live` / `ts` branch |

## Tests you're given

`tests/test_sources.py::test_classify_source_maps_digits_urls_and_paths`,
`tests/test_sinks.py::test_composite_calls_every_sink_even_when_one_says_stop`,
`tests/test_sinks.py::test_composite_close_reraises_the_first_failure_after_closing_all`,
`tests/test_cli.py::test_resolve_toggle_defaults_on_offline_and_off_live`

## Tests you write

- `CameraSource` when the device won't open → a clear `RuntimeError`, not a cryptic cv2 one
- `_derive_info` when the device reports `fps=0` → the fallback
- `--record` rejected on an offline source
- A live sidecar row carries `ts`; an offline row does not

## Milestone

```bash
uv run track --source 0                          # plain live preview, q to quit
uv run track --source 0 --track --conf 0.3       # live tracking
uv run track --source 0 --sidecar live.jsonl --record live.mp4
```

**End of month 2: a live object tracker.** Months 1–2 are the computer-vision half of the
project, and it's done.

## ADR to write

**ADR-0010 — live mode via camera/stream ingestion, mode inferred from `--source`.** Cover the
throughput consequences explicitly — that section is what makes it an honest ADR rather than a
feature announcement.

## Stuck?

`.scratch/live-mode/PRD.md` and its six issue files are the original spec for this exact week.
