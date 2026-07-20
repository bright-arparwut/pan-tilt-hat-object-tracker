# Viz ② — Full End-to-End Loop (all four components, one lap)

**Date:** 2026-07-05
**Status:** Ready to build (own session).
**Read first:** `2026-07-05-viz-shared-identity.md` — visual system, hard Artifact constraints, full
grounded fact base. This spec only describes what makes diagram ② unique.

## One-line job
Show **one complete lap of the closed feedback loop across all four physical components** — Mac,
Raspberry Pi, PCA9685 board, and the camera+servos on the platform — so the reader sees how sight
goes up, a command comes down, and the loop closes through the *physical world*.

## Audience & takeaway
The builder wanting the big picture with the hardware made explicit. The prior system-level artifact
drew the whole Pi as a single box; **this one explodes that box** into Pi-compute → PCA9685 → servos,
and makes the "the servo moves, so the camera sees something new" closure a visible arrow, not an
implied one.

## What it must show — four components in a ring/loop

Four nodes, each a labeled card, connected so the signal path forms a **closed loop** (not a straight
line). Suggested arrangement: Mac and Pi as the two big "compute" cards, with PCA9685 and the
camera+servos as the physical stage the loop passes through.

- **① Camera + servos (on the platform)** — USB camera + 2 servos (pan ch0 / tilt ch1), physically
  riding the pan-tilt platform. The loop's sensor *and* effector, on the same moving body.
- **② Mac — the brain** — YOLO Detector → ByteTrack → Target Selector (lock-first-id) → pixel error →
  Aim Controller → `UdpAimTransport`. All detection here.
- **③ Raspberry Pi 5 — the body** — Frame Streamer (MJPEG up) + Command Listener (`run_listener`,
  freshest-wins) + `ServoDriver`. No detection.
- **④ PCA9685 board** — 12-bit PWM chip at I²C `0x40`; turns the driver's writes into PWM pulses to
  the servos.

## The lap — number the legs (this IS a real sequence)

1. **Video UP [cyan]:** camera → MJPEG over HTTP (`multipart/x-mixed-replace`, port 8000) → Mac
   ingests via `--source http://<pi-ip>:8000/stream.mjpg` (existing `CameraSource`, no new code).
2. **Think [Mac]:** detect + track → confirmed Tracks → Target Selector latches the followed id →
   `error = target_center − frame_center` → Aim Controller `step()` → `AimCommand(pan_delta, tilt_delta)`.
3. **Command DOWN [amber]:** `UdpAimTransport.send` → one UDP JSON datagram
   `{"pan_delta","tilt_delta","seq"}` on port 9000 → Pi `run_listener` → freshest-wins → `apply_delta`.
4. **Drive [Pi → board]:** `ServoDriver` clamps to limits → `kit.servo[n].angle` → **I²C** writes to
   PCA9685 `0x40`.
5. **Move [board → servos]:** PCA9685 emits 50 Hz PWM → the two servos rotate the platform.
6. **Close the loop [physical]:** the camera rides the platform, so the move changes what the *next*
   frame sees → back to leg 1 with a smaller error.

## The two ideas to make visually loud
- **It's a ring, not a line.** The reader should immediately see a cycle. Draw leg 6 as a distinct
  "through the physical world" arrow (dashed / different texture) from the servos/platform back to the
  camera's field of view — the closure that makes it a control loop.
- **Latency lives in the network legs.** Put a `~50–200 ms latency inside the loop` marker on the
  cyan (up) and amber (down) legs, with a one-line "this is why a P→PID controller + a center
  deadzone exist instead of snapping to the target."

## Layout guidance
- Color the legs by path: cyan for video-up, amber for command-down, a neutral/steel treatment for
  the internal I²C→PWM legs (4–5), and a dashed accent for the physical closure (6).
- Wide screens: a genuine loop/ring layout (e.g. Mac top-left, Pi top-right, PCA9685 + servos across
  the bottom, camera bridging back up). Narrow screens: collapse to a vertical numbered flow 1→6 with
  a "loops back to 1" note at the end. Keep any wide diagram in an `overflow-x:auto` container.
- A compact legend: `cyan = video / sight (up)` · `amber = commands / motor (down)` ·
  `dashed = physical closure`.

## Out of scope
Byte-level I²C/PWM math (that's diagram ①) and the software/library/chip ownership boundaries (diagram
③). Keep the components as boxes with their role; don't unfold the register-level detail here.
