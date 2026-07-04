# Pan-Tilt Tracking Turret — Design & Learn-by-Building Roadmap

**Date:** 2026-07-04
**Status:** Approved design — ready for implementation planning
**Author:** Bright (with Claude)

## Purpose

Add a **physical body** to the existing `object_tracker` project: a pan-tilt turret that
physically rotates to keep a detected/tracked object centered in the camera frame. This is a
classic **visual-servoing** ("eye-in-hand") robotics problem.

The secondary, equally-weighted goal is **learning**: this is the author's on-ramp to
Raspberry Pi / IoT / robotics. The author has a computer-science background and **no formal
hardware/electronics training is required** — the chosen HAT abstracts the analog electronics
into "write an angle over I²C." The one genuinely new discipline is **control theory** (the
feedback loop), which is algorithmic and squarely in CS territory.

## Decisions (locked)

| Decision | Choice | Rationale |
|---|---|---|
| Where vision runs | **Mac = brain, Pi = actuator** | Reuses the existing `object_tracker` code unchanged; best FPS; small integration surface. |
| Camera mounting | **On the pan-tilt platform** (moves with it) | True "keep target centered" closed-loop tracking — the interesting version. |
| Learning style | **Phased: build a milestone, learn its theory** | Learn-by-doing with intent; theory becomes load-bearing exactly when needed. |
| Hardware in hand | Pi 5 + Waveshare Pan-Tilt HAT + USB camera | Fixed constraints the design is tailored to. |
| v1 transport | MJPEG video up + simple UDP/TCP command socket | Dead-simple, well-documented; optimize latency only if it hurts (Phase 5). |

## System architecture

Because the camera physically lives on the Pi (mounted on the turret) but the detector lives on
the Mac, frames travel **up** and aim commands travel **down**:

```
        ┌────────────────────────── Pi 5 (the "body") ─────────────────────────┐
        │  USB cam (on turret)  ──capture──►  frame streamer ──MJPEG/UDP──┐     │
        │                                                                  │     │
        │  PCA9685 (I²C) ◄── servo driver ◄── command listener ◄──────┐    │     │
        └──────────────────────────────────────────────────────────┼────┼─────┘
                                                                     │    │
                          aim command (pan_delta, tilt_delta)        │    │  video
                                                                     │    ▼
        ┌────────────────────────── Mac (the "brain") ──────────────┴──────────┐
        │  receive frame ─► object_tracker (YOLO + ByteTrack) ─► pick target    │
        │       ─► error = (target_center − frame_center) ─► controller ─► cmd  │
        └───────────────────────────────────────────────────────────────────────┘
```

### The core mental model: a feedback loop with latency

The camera sees the target off-center → the Mac computes a pixel **error** → a **controller**
converts that error into a servo move → the servo moves → the camera's view shifts → new error.
Because video and commands cross a network, there is **~50–200 ms of lag inside the loop**. That
single fact is why you cannot "snap the servo to the target" — you would overshoot and oscillate.
It is the entire reason a controller (proportional → later PID) exists. This is the central thing
to learn from this project.

### Integration with the existing codebase

The `object_tracker` pipeline already emits tracked boxes with center points (that is what draws
the `#id` labels and the zoom inset). The turret is therefore **a new output sink**: the same way
`sinks.py` writes annotated video / JSONL, an **actuator sink** consumes the selected target's
center and emits an aim command. This keeps disruption to the existing, tested pipeline minimal.

## Component design (units, each with one purpose)

Each unit is independently understandable and testable:

- **`servo driver` (Pi)** — Wraps the Waveshare HAT / PCA9685. Input: a clamped `(pan_angle,
  tilt_angle)`. Responsibility: talk I²C, enforce mechanical limits. Depends on: the HAT library.
- **`frame streamer` (Pi)** — Captures the USB camera and streams frames (MJPEG) to the Mac.
  Depends on: OpenCV / camera.
- **`command listener` (Pi)** — Receives `(pan_delta, tilt_delta)` over a socket, applies them to
  the servo driver's current angle (clamped). Depends on: servo driver.
- **`controller` (Mac) — the heart** — A **pure function**:
  `(pixel_error, gains, prev_state) → (command, new_state)`. Proportional in Phase 3, PID in
  Phase 4. No I/O, no mutation → fully unit-testable on the Mac with zero hardware.
- **`target selector` (Mac)** — Given the frame's tracked boxes (multiple `#id`s), chooses which
  one to follow (policy: locked-id / largest / nearest-center). Pure, testable.
- **`actuator sink` (Mac)** — Glue: pulls the selected target from the pipeline, runs the
  controller, ships the command down. Mirrors the existing `sinks.py` shape.

## Phased build-and-learn roadmap

Each phase ends with something that **runs**, and teaches **one** concept.

| Phase | Build | Concept learned | Done when |
|---|---|---|---|
| **0. Pi foundations** | Headless Pi 5: SSH, Python venv, enable I²C | Embedded Linux basics (HAT hides the electronics) | SSH works; `i2cdetect` shows the HAT |
| **1. Make it move** | `servo.py`: center, sweep, clamp pan/tilt via the HAT | PWM & servo angles over I²C; why limits matter | A keyboard teleop script aims the turret by hand |
| **2. Eye → brain** | Stream USB frames Pi→Mac (MJPEG); run existing tracker on them | Video streaming & real measured latency | Mac shows `#id` boxes on the live turret feed |
| **3. Close the loop** | Actuator sink + **P controller**: pixel error → servo delta, with deadzone + clamp | Coordinate mapping (pixels→angles) + proportional control; why P alone overshoots | Turret roughly follows a target (jittery) |
| **4. Tame the jitter** | Upgrade P → **PID**; rate-limit & smooth | PID tuning — what I and D each fix; overshoot vs. lag | Smooth, stable tracking; no oscillation |
| **5. (Stretch) Robustness** | Lost-target search, target-selection policy, lower-latency transport, optional fast inner loop on the Pi | Real-time control architecture; two-rate loops; degraded modes | Recovers when the target leaves frame |

The pivotal transition is **3 → 4**: the "aha" of control theory. You will *see* the P-only turret
overshoot and hunt, then watch the D term calm it. Feeling PID misbehave before reading about it
makes it stick.

## Hardware notes & gotchas (specific to this kit)

- **Pi 5 + I²C is the happy path.** The HAT uses I²C (PCA9685), so it sidesteps the Pi 5
  `RPi.GPIO` PWM breakage entirely. Enable I²C via `raspi-config` first.
- **Power is the #1 silent failure.** Servos draw current spikes when moving; a weak supply causes
  brownouts that reboot the Pi or make servos twitch. Use a proper 5V/5A Pi 5 supply and verify how
  the HAT feeds servo power. Mystery resets almost always trace here.
- **Clamp servo angles in software** to the HAT's mechanical limits — first thing written in
  Phase 1 — or risk stalling/stripping a servo.
- **Cable management:** the USB-cam cable rides a moving platform; leave slack so the turret does
  not fight its own wire.

## Risks

- **Latency-induced oscillation** — mitigated by the deadzone + the P→PID progression (Phases 3–4).
- **"Which target?"** — ByteTrack yields multiple `#id`s; a selection policy is required. Decided
  in Phase 3, isolated in the `target selector` unit.
- **Sign errors** — pan/tilt moving the *wrong* direction is the classic first bug; the Phase 1
  teleop script nails the sign before the loop is closed.

## Testing strategy

Fits the project's existing tested / immutable style:

- **`controller`** — pure function; unit-tested on the Mac with zero hardware, no mutation
  (`(error, gains, state) → (command, new_state)`).
- **`target selector`** — pure; table-driven unit tests over synthetic box sets.
- **`servo driver`** — verified with the manual teleop harness from Phase 1.
- **`frame streamer`** — verified standalone (view the stream) before wiring into detection.
- **Integration** — only the final closed loop needs the physical rig.

## Resources (ordered by phase)

- *Raspberry Pi Cookbook* — Simon Monk → Phases 0–2 (recipe-style, matches the per-phase approach).
- **Waveshare Pan-Tilt HAT wiki** + **Adafruit PCA9685 servo guide** (primary docs) → Phase 1.
- **PyImageSearch — "Pan/tilt face tracking with a Raspberry Pi"** (Adrian Rosebrock) → *literally
  this project* with a PID controller; the best single practical reference. Phases 3–4.
- **Brett Beauregard — "Improving the Beginner's PID"** blog series → clearest hands-on PID
  explanation; Arduino-flavored but ports straight to Python. Phase 4.
- *Feedback Systems* — Åström & Murray (**free PDF**) → proper controls-theory footing behind PID.
- *Modern Robotics* — Lynch & Park (**free, with video course**) → optional deeper dive on
  coordinate frames if the robotics side grabs you.

## Out of scope (v1 / YAGNI)

- Low-latency transport (WebRTC/gRPC/GStreamer) — only if measured lag hurts (Phase 5).
- Running detection on the Pi (rejected: Mac = brain was chosen).
- Multi-target simultaneous tracking, re-identification across occlusion, autonomous search
  patterns beyond a simple lost-target recenter.

## Next step

Turn this into a concrete implementation plan, starting with Phases 0–1 (Pi foundations + make it
move) via the writing-plans workflow.
