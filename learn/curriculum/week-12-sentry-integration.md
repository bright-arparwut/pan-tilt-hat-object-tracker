# Week 12 — Sentry mode & full integration

**Hours:** 4 Mac + 3 `[Pi]` · **Milestone:** it sweeps, finds you, locks on

## Why this week

Week 11's turret does something unsatisfying when it loses you: **nothing**. It sits there
aimed at empty space.

Fixing that runs into a genuinely interesting constraint. To sweep, the host needs to know
where the turret is pointing. But the wire carries **only relative nudges**, and the Pi
**never reports its pose**. There is no feedback channel at all.

So you dead-reckon: the host keeps an *estimate*, accumulates every delta it ships, and clamps
with its own mirror of the Pi's limits. The estimate will drift. The interesting part is what
you do about that — and the honest answer the project reaches is *"pan self-corrects, tilt
doesn't, and we accept it."* Knowing which errors to fix and which to document is a senior
engineering skill.

## Concepts

- **Control without feedback (open-loop / dead reckoning).** Track your own commands as a proxy
  for state. Always drifts; sometimes that's fine.
- **Why pan self-corrects and tilt doesn't.** Every half-sweep drives pan into a *hard
  mechanical limit*. The servo stops there and so does the estimate — **the limit re-zeroes the
  drift**, twice per sweep, for free. Tilt just holds a patrol angle and never touches a stop,
  so its error accumulates unbounded-but-slowly. The project accepts it. Make sure you can
  explain this; it's the best idea in the codebase.
- **Mirrored constants, deliberately not shared.** `SENTRY_PAN_MIN_DEG` duplicates the Pi's
  `PAN_MIN_DEG` *by hand*, with a comment saying so. DRY says extract; ADR-0013 says two
  deployables must not share a module. Which wins, and why?
- **Triangle-wave sweep.** Constant speed, flip direction at each bound. Per-step magnitude
  capped by `max_delta_deg` so a pipeline stall can't produce a violent jump.
- **Grace period.** Don't sweep the instant a track blinks out — wait `SENTRY_GRACE_S` (2s).
  Prevents thrashing between track and sweep on a flickering detection.
- **Hand-back on the very next frame.** The moment a track appears, tracking resumes. No
  "finish the sweep" state. Simplicity as a feature.
- **The Pi can't tell the difference.** Sweep nudges go down the same wire as aim nudges, as
  ordinary `AimCommand`s. The actuator stays dumb. That's the design holding.
- **MJPEG streaming.** `multipart/x-mixed-replace` — the oldest trick on the web, and
  `cv2.VideoCapture` opens it as a plain URL, so week 8's `CameraSource` needs **zero new
  code**. Two capture paths (USB via OpenCV, CSI via Picamera2) behind one `Camera` Protocol,
  with the Picamera2 import lazy — the week-9 pattern again.

## Sessions

**Session 1 (2h, Mac) — the state machine.** `sentry.py`: `SentryState` (pose estimates,
direction, unlocked timer), `step` (one unlocked frame → deltas + new state), `observe_aim`
(a locked frame folds its deltas into the estimates and resets the grace timer). Pure, frozen
dataclasses, same shape as `aim_controller`. Test it entirely with numbers.

**Session 2 (1h, Mac) — glue.** The `else` branch in `ActuatorSink.show`, and `observe_aim` on
the locked path. ~10 lines. Then the `SentryConfig` constants.

**Session 3 (2h, Mac + `[Pi]`) — the streamer.** `_encode_part` (pure, testable), the `Camera`
Protocol, `_open_camera` / `_open_csi_camera`, and `run_streamer`. The HTTP handler scaffolding
is given. Then `main.py`'s threading: the **listener owns the main thread** (it moves motors);
the streamer is a **daemon thread**; SIGINT/SIGTERM set a stop `Event` both planes poll
cooperatively. Understand why signals must not raise into the listener.

Verify on the Pi: `uv run turret` then open `http://<pi-ip>:8000/stream.mjpg` in a browser.

**Session 4 (2h, `[Pi]`) — the closed loop.**

```bash
# Pi
uv run turret --port 9000 --stream-port 8000        # add --csi for a camera module
# Mac
uv run track --source http://<pi-ip>:8000/stream.mjpg --track --turret <pi-ip>:9000
```

Video up, commands down. Walk away — watch it sweep. Walk back — watch it lock on.

## Files you implement

| File | What |
|---|---|
| `object_tracker/turret_sink/sentry.py` | `SentryState`, `step`, `observe_aim` |
| `object_tracker/turret_sink/actuator_sink.py` | the sentry branch |
| `object_tracker/config.py` | `SentryConfig` + the `SENTRY_*` constants |
| `turret/turret_pi/streamer.py` | `_encode_part`, `Camera`, `_open_camera`, `_open_csi_camera`, `run_streamer` |
| `turret/turret_pi/main.py` | `_start_streamer_thread`, signal handling |

## Tests you're given

`tests/test_sentry.py::test_no_sweep_until_the_grace_period_elapses`,
`::test_pan_sweeps_left_first_and_flips_at_the_bound`,
`::test_tilt_relocates_monotonically_to_default_without_overshoot`,
`::test_observe_aim_resets_the_grace_timer_and_rearms_left`,
`turret/tests/test_streamer.py::test_encode_part_frames_a_jpeg_as_a_multipart_chunk`

## Tests you write

- A stall (huge `dt`) is capped at `max_delta_deg` — no violent jump
- Pan estimate never exceeds its clamps, over a full sweep cycle
- `observe_aim` clamps tilt at its own bounds
- `run_turret` skips the streamer under `--no-stream` and still recenters on exit

## Milestone

**The full closed loop.** Record it.

## ADR to write

**ADR-0014 — sentry mode: host-side sweep on a dead-reckoned pose.** The section that matters
is the drift analysis — pan self-corrects at the limits, tilt's bounded drift is accepted.
Write that reasoning out properly.

## Retrospective (do this, 1h)

Now read the root repo's `CONTEXT.md` end to end. Every term in it should be something you
built. Then:

1. Diff your 14 ADRs against the originals. Where did you decide differently? Were you wrong,
   or just different?
2. Compare your `tests/` against the root repo's. What did they test that you didn't think of?
3. Re-read your week-5 toy tracker. You'd write it differently now — how?
4. Write one page: what you'd design differently if you started over.

That last one is the real deliverable of twelve weeks.
