# Week 9 — Servos & the Pi-side split

**Hours:** 5 Mac + 2 `[Pi]` · **Milestone:** teleop moves the real turret; limits measured

## Why this week

Month 3 is a different discipline. Software bugs print a stack trace; **hardware bugs strain a
motor, brown out the Pi, and strip a gear.** Everything this week is arranged so the dangerous
parts are the last thing you do and the smallest thing you do.

That arrangement *is* the architecture: a pure `clamp_angles` you test on the Mac, a
`ServoDriver` whose hardware SDK is behind a **lazy import** and an **injectable `kit`**, so the
only code that has never run before you plug in the HAT is the SDK call itself.

## Your workflow from here

```
write + unit-test on the Mac  →  git push  →  ssh pi  →  git pull  →  uv sync  →  run
```

The Mac never installs `adafruit-blinka`; the Pi never installs `torch`. Two packages, one
repo (ADR-0013). Keep a terminal SSH'd into the Pi all evening — the loop is fast.

## Concepts

- **I²C and the PCA9685.** A 16-channel PWM driver at address `0x40`. `i2cdetect -y 1` is your
  "is it even there" check. Pan is channel 0, tilt is channel 1.
- **Servo control is pulse width, not degrees.** ~500–2500µs maps to 0–180°. The
  `adafruit_servokit` library does the conversion; you set the range because cheap servos vary.
- **Mechanical limits ≠ electrical limits.** The servo will happily accept 0–180°, but the
  *assembled bracket* stops earlier. Commanding past the stop **stalls** the motor: it buzzes,
  draws a current spike, and never settles. On this build: pan 0–180° (full), tilt **20–115°**.
  You must re-measure these for your own build.
- **Safe pose.** `CENTER` is the *mid-range of the measured limits* — pan 90°, tilt 67.5° — not
  a raw 90/90. Write to it on startup and on shutdown.
- **Lazy imports as a portability tool.** `from adafruit_servokit import ServoKit` lives
  *inside* `__init__`, reached only when `kit is None`. That one line is why every Pi module
  imports and unit-tests on your MacBook.
- **Dependency injection for hardware.** `ServoDriver(kit=FakeKit())` gives you full test
  coverage of the accumulate-clamp-write logic with no hardware.

## Sessions

**Session 1 (2h, Mac) — the pure half.** `ServoAngles` (frozen), `clamp_angles`, and the limit
constants. ~20 lines, entirely pure. Test every boundary.

**Session 2 (3h, Mac) — the driver, fake-first.** `ServoDriver` against a **fake kit** you
write in the test file. `apply_delta` (accumulate onto current pose → clamp → write both
channels), `recenter`, the `current` property. Note the single `_write` path and the
"replaced, never mutated" comment. Also write `teleop.key_to_delta` — pure, WASD → deltas.

**Session 3 (2h, `[Pi]`) — hardware bring-up.** Now, and only now, touch the hardware. Follow
`../turret/DEPLOY.md` Phase 0. Then:

```bash
ssh pi@raspberrypi.local
cd repo/learn/turret && git pull && uv sync --extra hardware
sudo i2cdetect -y 1            # expect 0x40 — the gate. Nothing proceeds without it.
uv run python -m turret_pi.teleop
```

Nudge toward each extreme with WASD. **The instant it strains or buzzes, back off.** The last
freely-reached angle is your limit. Write your four measured numbers into `servo.py`.

If an axis moves the wrong way, flip `PAN_SIGN` / `TILT_SIGN`. This is the classic first bug
and it's supposed to happen to you.

## Files you implement

| File | What |
|---|---|
| `turret/turret_pi/servo.py` | `ServoAngles`, `clamp_angles`, limit constants, `ServoDriver` |
| `turret/turret_pi/teleop.py` | `key_to_delta` (the TTY loop is given) |

## Tests you're given

`turret/tests/test_servo.py::test_clamp_holds_an_angle_inside_the_limits`,
`::test_clamp_pins_tilt_to_the_measured_bracket_limits`,
`::test_apply_delta_accumulates_onto_the_current_pose_and_clamps`,
`::test_recenter_writes_the_safe_center_pose`

All four run on your Mac with a fake kit. That's the point of the week.

## Tests you write

- A delta far past the limit clamps rather than raising
- `_write` is called exactly once per `apply_delta` (both channels, one write path)
- `key_to_delta` on an unknown key → `(0.0, 0.0)`
- Construction writes `CENTER` before accepting any delta

## Milestone

The turret physically moves under WASD, stops cleanly at limits you measured yourself, and
your four constants are committed.

## ADR to write

**ADR-0013 (part 1) — pan-tilt turret as an Actuator Sink; the Pi is the actuator, the Mac is
the brain.** Argue the alternative: why *not* run YOLO on the Pi?

## Safety checklist

- [ ] 5V/**5A** supply (servo current spikes brown out an underpowered Pi)
- [ ] Limits measured on **your** bracket, not copied from `DEPLOY.md`
- [ ] Camera cable routed with slack so the platform doesn't fight its own wire
- [ ] Never hold a servo against its stop "just to see"
