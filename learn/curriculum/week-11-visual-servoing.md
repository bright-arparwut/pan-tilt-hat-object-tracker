# Week 11 — Visual servoing (P → PID)

**Hours:** 5 Mac + 3 `[Pi]` · **Milestone:** the turret follows you, without oscillating

## Why this week

This is where the two halves meet. The camera rides the platform the camera is aiming — so
seeing and moving are **one closed loop**. Move wrong and the next frame is wrong, and the loop
amplifies its own mistake.

You have three pure units to write and one piece of glue. Notice how small the glue is: 78
lines, no decisions in it. Every decision lives in a pure function you can test on a plane.

## Concepts

- **The error signal.** `error = target_centre − frame_centre`, in pixels. +x is right, +y is
  **down** (image coordinates). If the target is right of centre, pan right. That's the whole
  idea; everything else is how *much*.
- **THE SIGN FLIP.** `tilt_delta` is **+up**, but image +y is **down**. So
  `tilt_delta = −kp · error_y`. The ADR calls this "the classic first bug" and it is: your
  turret will look *down* when the target is *up*, and it will run away to the limit within a
  second. There is a given test for exactly this. Respect it.
- **Proportional control.** `output = kp · error`. Too small: it lags and never catches up. Too
  large: it overshoots, and next frame's error has the opposite sign — **oscillation**.
- **Why the network makes P insufficient.** There's ~50–200ms between seeing an error and the
  servo moving. A P controller tuned aggressively enough to be responsive *will* oscillate,
  because it keeps correcting for an error already being corrected. Hence D.
- **PID, one term at a time.** P = respond to the error now. I = accumulate persistent error
  (kills steady-state offset; watch for integral windup). D = respond to the *rate of change*
  (damps overshoot — the term that fixes your latency problem). This project ships
  `ki = kd = 0.0` and the same `step` function becomes PID purely by which gains are nonzero.
  That's a nice design: no phase-3/phase-4 code fork.
- **Deadzone.** Below ~6px of error, command zero. Without it the turret jitters permanently
  around centre, hunting noise.
- **Slew clamp.** Cap any single command at `max_delta_deg`. A pipeline stall means a huge `dt`
  means a violent snap — unless you clamp.
- **Lock-first-id.** `select_target` keeps the current id while present, else takes the
  smallest present id (= first-seen, since ids are monotonic — the week-7 idiom again).
  Deterministic, no per-frame target flip-flopping.
- **The Actuator Sink is a `FrameSink`.** It never draws. It composes with the window and the
  recorder exactly like any other sink, and the loop has no idea it's aiming a motor. Week 8's
  seam, cashed in.

## Sessions

**Session 1 (1h, Mac) — the selector.** `target_selector.select_target`. 18 lines, pure,
table-driven tests. An easy start to a hard week.

**Session 2 (2.5h, Mac) — the controller.** `AimCommand`, `AimControllerState`, `_pid_axis`,
`step`. Pure and fully testable: feed synthetic pixel errors, assert the deltas. Get the
deadzone, the clamp, the integral accumulation, the `dt == 0` guard, and **the tilt sign** all
covered before any hardware sees it.

**Session 3 (1.5h, Mac) — the glue + dry run.** `ActuatorSink` and the `--turret` CLI wiring
(`_parse_turret_target`, `_maybe_add_turret`). Then dry-run the whole loop with no Pi:

```bash
uv run python scripts/fake_turret_listener.py --port 9000     # terminal 1
uv run track --source 0 --track --turret 127.0.0.1:9000       # terminal 2
```

The fake listener **reverse-maps each delta back to the implied pixel error**. Move in front of
your webcam and read the numbers. Verify the signs here, on screen, before a motor can act on
them.

**Session 4 (3h, `[Pi]`) — tune on hardware.** Deploy, run the real loop, and tune:

```bash
# Pi:   uv run turret --port 9000 --no-stream
# Mac:  uv run track --source 0 --track --turret <pi-ip>:9000 --turret-kp 0.02
```

Start `kp` **low** (0.02). Raise it until it tracks responsively. Keep raising until it
oscillates — *find that point deliberately*, it teaches more than a working value. Then back
off ~30%, or add `--turret-kd` to damp it and keep the higher `kp`.

Log your gains and what each did. That table is the week's real artefact.

## Files you implement

| File | What |
|---|---|
| `object_tracker/turret_sink/target_selector.py` | `select_target` |
| `object_tracker/turret_sink/aim_controller.py` | `AimCommand`, `AimControllerState`, `_pid_axis`, `step` |
| `object_tracker/turret_sink/actuator_sink.py` | `ActuatorSink` (without the sentry branch) |
| `object_tracker/turret_sink/__init__.py` | the re-exports |
| `object_tracker/cli.py` | `--turret*` flags, `_parse_turret_target`, `_maybe_add_turret` |
| `object_tracker/config.py` | `AimGains`, `TurretConfig` |

## Tests you're given

`tests/test_target_selector.py::test_select_target` (table-driven, 7 cases),
`tests/test_aim_controller.py::test_tilt_inverts_the_sign_of_y_error`,
`::test_error_inside_deadzone_produces_zero_command`,
`::test_output_clamps_at_positive_max_delta`,
`tests/test_actuator_sink.py::test_show_always_returns_true`

## Tests you write

- Integral accumulates across steps (`ki` only)
- Derivative responds to *change*, not magnitude (`kd` only, constant error → 0)
- `dt == 0` doesn't divide by zero
- `ActuatorSink` sends nothing when no track is present
- `_parse_turret_target` on `"host"`, `"host:9000"`, and malformed input

## Milestone

**The turret follows you around the room, smoothly.** Record a video of it — this is the payoff
of eleven weeks.

## ADR to write

**ADR-0013 (part 3) — Aim Controller: proportional first, PID when the loop is seen to
overshoot.** Write down *why* you don't start with PID. (Hint: three untuned gains is three
times the search space, and you can't tell which one is wrong.)

## When it oscillates

It will. Work through it in this order:
1. **Runaway to the limit in <1s** → sign error. Check tilt first.
2. **Fast buzzing around centre** → deadzone too small, or `kp` far too high.
3. **Slow overshoot-and-return** → `kp` slightly too high for the latency. Add `kd`.
4. **Never quite centres** → steady-state error. A little `ki` (watch for windup).
