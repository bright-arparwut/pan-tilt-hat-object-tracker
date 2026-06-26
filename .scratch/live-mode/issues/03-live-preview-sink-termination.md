# 03 — Live Preview sink + unified termination / cleanup

Status: done

## Goal

Add the **`WindowSink`** (Live Preview) — a `FrameSink` that shows annotated frames in an
on-screen window and reports when the viewer wants to stop — plus a **`CompositeSink`** that
fans one frame out to several sinks (for `--record` = window + file). Unit-tested headlessly;
CLI wiring is 04.

## Decisions (from grilling session, ADR-0010)

- **`WindowSink.show(frame)`** calls `cv2.imshow` + `cv2.waitKey(1)` and returns **false** when
  the user presses `q` **or** closes the window (`getWindowProperty(..., WND_PROP_VISIBLE) < 1`),
  true otherwise. `close()` → `cv2.destroyWindow`.
- **`CompositeSink(sinks)`** — `show()` calls every child and returns the **logical AND** of
  their results (the window governs stop; `VideoFileSink` always returns true). `close()` closes
  all children (best-effort; one failure still closes the rest).
- **Single teardown path.** `run()` already wraps the loop in `try/finally` (01); `q`,
  window-close, EOF, and `KeyboardInterrupt` (`Ctrl-C`) all funnel through it →
  `sink.close()` + `source.release()` (+ sidecar close). No leaked capture/window.
- A small **window title** (e.g. `object-tracker — q to quit`) and the source label; keep an
  optional processed-fps overlay out of scope unless trivial.

## Tasks

- `sinks.py` — `WindowSink(window_name)` and `CompositeSink(list[FrameSink])`; keep the
  `show -> bool` / `close()` contract from 01.
- `pipeline.py` — confirm the `finally` releases source + closes sink even on
  `KeyboardInterrupt` (add a test that injects `Ctrl-C` mid-loop via a sink/source that raises).
- Tests: `WindowSink.show` returns false when `cv2.waitKey` is monkeypatched to return `ord('q')`
  and when the window-visible property is monkeypatched `< 1`, true otherwise; `imshow` is
  patched (no real window). `CompositeSink` fans out to two fakes, returns AND, and closes both
  even if the first `close()` raises. A `run()` test asserts cleanup runs on `KeyboardInterrupt`.

## Acceptance

1. `WindowSink.show` returns false on `q` and on window-close, true otherwise; `close()`
   destroys the window. (All cv2 calls monkeypatched — no real window in CI.)
2. `CompositeSink` returns the AND of children and closes every child even if one raises.
3. `run()` releases the source and closes the sink on `q`, EOF, **and** `KeyboardInterrupt`
   (asserted).
4. `uv run pytest` green headless.

## Depends on

01 (the `FrameSink` Protocol).

## Refs

ADR-0010 (§The seams, §Consequences — clean shutdown). PRD §Target architecture.
