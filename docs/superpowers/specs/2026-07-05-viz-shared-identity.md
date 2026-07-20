# Turret Visualizations — Shared Identity & Fact Base

**Date:** 2026-07-05
**Status:** Ready — the shared brief for the three hardware-architecture visualizations.
**Read this first**, then the per-diagram spec:
- `2026-07-05-viz-1-signal-translation-chain-spec.md`
- `2026-07-05-viz-2-end-to-end-loop-spec.md`
- `2026-07-05-viz-3-layered-stack-spec.md`

Each diagram is built in its **own session** as a standalone claude.ai **Artifact** (HTML). This
file gives every session the identical visual system, the hard Artifact constraints, and the
grounded technical facts, so the three read as one coherent family (and match the existing
`turret-architecture.html` system-level artifact).

## How to build (every session)

1. **Load the `artifact-design` skill first** (it calibrates the treatment) — then build.
2. Write ONE self-contained HTML file. Publish it with the **Artifact** tool (favicon + one-line
   description). Suggested favicons: ① `🎯`/`⚙️`, ② `🔁`/`🎯`, ③ `🧱`/`📚` — pick one, keep it stable.
3. Treatment: a **polished engineering-brief / control-panel schematic**. Utilitarian but crafted —
   real hierarchy, considered spacing. No flashy oversized hero, no AI-default cream-serif look.

## Hard Artifact constraints (non-negotiable)

- Emit ONLY page content: a `<title>`, one `<style>` block, and body markup. Do **NOT** emit
  `<!doctype>`, `<html>`, `<head>`, or `<body>` — the platform wraps the file at publish time.
- Fully self-contained under a strict CSP: **no external anything** — no CDN, no webfont URLs, no
  remote images/scripts/fetch. All CSS inline in the `<style>`. **System font stacks only.**
- Responsive: the page body must **never** scroll horizontally. Wrap any wide diagram/table/code
  in its own `overflow-x:auto` container. Multi-column layouts stack on narrow screens.
- Accessible: semantic HTML, visible `:focus-visible`, honor `prefers-reduced-motion` (guard any
  animation), double-quote attributes, close every tag.
- Motion: tasteful only — a guarded load-reveal at most. No gratuitous animation.

## Visual system (identical across all three)

```
--ink:      #0e1418   /* page ground — near-black slate, slight blue-green bias */
--panel:    #161d23   /* raised surfaces / cards */
--panel-2:  #1c252c   /* nested surfaces */
--hairline: #2a343c   /* borders, grid lines */
--text:     #e6edf1   /* primary, cool off-white */
--muted:    #8b9aa5   /* secondary */
--teal:     #45c8b8   /* primary accent / phosphor */
--cyan:     #4aa8e0   /* VIDEO / sight / Pi->Mac (the "up" path) */
--amber:    #e8a33d   /* COMMANDS / motor / Mac->Pi (the "down" path) */
--ok:       #57b98a   /* status: built */
--rust:     #c9704a   /* status: pending */
--sans:     system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
--mono:     ui-monospace, "SF Mono", Menlo, Consolas, monospace;
```

Rules:
- **Color-coding is load-bearing:** cyan = everything about video/sight/up; amber = everything
  about commands/motor/down. Keep it consistent. `--ok`/`--rust` are status only, never accents.
- **Monospace for all data** — numbers, angles, µs, ticks, registers, ports, addresses, code
  identifiers — with `font-variant-numeric: tabular-nums`. Sans for headings and prose.
- Uppercase eyebrow labels in mono with letter-spacing (~0.12–0.18em). Headings `text-wrap: balance`.
- Body measure ~65ch. Ground it in radial slate gradients if you like (subtle).

## Grounded fact base (accurate — use these exact values)

### The four components
- **Mac — the brain (host).** Runs the existing `object_tracker` pipeline: YOLO Detector →
  ByteTrack Tracker → Target Selector (lock-first-id) → pixel error → Aim Controller (P now, PID
  later) → Actuator Sink → `UdpAimTransport`. **All detection runs here.**
- **Raspberry Pi 5 — the body (actuator).** Runs `turret_pi`: the Frame Streamer (MJPEG, pending),
  the Command Listener (`run_listener`, built & tested), and the `ServoDriver` (pending). **No
  detection here.**
- **Waveshare Pan-Tilt HAT · PCA9685** — a 16-channel, 12-bit PWM chip on the Pi's I²C bus at
  address **`0x40`**. Sits on the GPIO header. Drives the servos. (I²C sidesteps the Pi 5 RPi.GPIO
  PWM breakage.)
- **2× servo + USB camera** — pan = **channel 0**, tilt = **channel 1**; the USB camera is mounted
  **on the moving platform**, so aiming and seeing are one closed loop (eye-in-hand visual servoing).

### The two channels
- **Video UP (Pi → Mac) [cyan]:** USB camera → MJPEG-encoded → served over HTTP
  (`multipart/x-mixed-replace`) by `turret_pi.streamer`. Mac ingests with
  `--source http://<pi-ip>:<port>/stream.mjpg` — the existing `CameraSource` (`cv2.VideoCapture`)
  opens it with **zero new Mac code**. Transport: HTTP over TCP. Default stream port **8000**.
- **Aim Commands DOWN (Mac → Pi) [amber]:** UDP, fire-and-forget, one JSON datagram per command:
  `{"pan_delta": <deg>, "tilt_delta": <deg>, "seq": <int>}`. Default UDP port **9000**.
  `pan_delta` is +right, `tilt_delta` is +up (image-relative). Mac side: `UdpAimTransport`. Pi side:
  `run_listener` → decode → freshest-command-wins (drops stale/duplicate by `seq`, recovers across a
  quiet gap) → `ServoDriver.apply_delta`.

### The signal chain — one command becoming motion (worked example, arithmetic is correct)
Given the turret is currently at **pan = 45°** and an Aim Command arrives with **pan_delta = +2.0°**:

| Stage | Owner | In → Out |
|---|---|---|
| Aim Command | Mac (over UDP) | `pan_delta = +2.0°` (relative nudge) |
| **ServoDriver** | **our code** | `45° + 2° = 47°` → `clamp_angles` (limits 0–180°) → **`47°` absolute**; calls `kit.servo[0].angle = 47` |
| **ServoKit / pca9685** | **downloaded library** | `47°` → pulse width `500 + (47/180)×2000 ≈ 1022 µs` → duty `1022/20000 = 5.1%` at 50 Hz → 12-bit tick `0.051×4096 ≈ 209` → I²C register writes (`LED0_ON=0`, `LED0_OFF=209`) to `0x40` |
| **I²C bus** | wiring | register bytes travel to address `0x40` |
| **PCA9685** | chip on the HAT | emits a **~1022 µs HIGH pulse every 20 ms** (50 Hz) on channel 0 |
| **Servo** | the motor | internal circuit turns pulse width → **shaft ≈ 47°** |

Constants: servo range **0–180°**, pulse **~500–2500 µs** (per-servo, calibrated in Phase 1),
PWM **50 Hz** (period **20 000 µs**), PCA9685 resolution **12-bit / 4096 steps**. The **degrees
boundary** is the key idea: our code produces `47°`; the library does everything below that.

### The closed feedback loop
Camera on the platform sees the target off-center → Mac computes pixel error → controller maps it
to a servo nudge → UDP down → Pi listener → ServoDriver → PCA9685 → servos move → the camera (on the
platform) shifts → next frame's error is smaller. Because video + commands cross the network there
is **~50–200 ms of latency inside the loop** — the reason an Aim Controller (P→PID) plus a center
deadzone exist instead of snapping to the target (a naive snap oscillates).

### Build status (for any status cues)
Built & tested: everything Mac-side; Pi-side `wire.decode`, `ServoAngles`/`clamp_angles`, the
Command Listener. Pending (needs the hardware): `ServoDriver` (I²C, Phase 1), the MJPEG streamer
(Phase 2), `main.py`. HAT SDK chosen: **Adafruit `adafruit-circuitpython-servokit`** (speaks in
degrees). Reference: ADR-0013 and `2026-07-04-pan-tilt-tracking-turret-design.md`.
