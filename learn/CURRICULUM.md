# 12-week curriculum — object-tracker from scratch

**Budget:** 5–8 hrs/week, ~80 hrs total.
**Hardware:** Pi 5 + Waveshare Pan-Tilt HAT + camera, from week 9. Development stays on the
Mac; `[Pi]` hours are deploy-and-verify sessions.

## The spine

Two ideas carry the whole project. Everything else is detail.

**1. Pure core + thin I/O shell.** Every hard module splits into a pure function you can
test on a plane with no hardware, wrapped in a thin shell that owns the socket / the I²C bus
/ the window. `handle_datagram` inside `run_listener`. `aim_controller.step` inside
`ActuatorSink`. `clamp_angles` inside `ServoDriver`. This is *why* 5,300 lines of a robotics
project are unit-testable on a MacBook.

**2. Three Protocol seams.** `Detector`, `FrameSource`, `FrameSink`. Every capability the
project has — offline or live, sliced or plain, to a file or a window or a motor — is a
consequence of those three interfaces. The weeks are ordered so you **feel the pain each
seam solves before you're allowed to introduce it**. You will write `pipeline.run` against a
concrete file reader in week 1 and be made to generalise it in week 8. That's deliberate.

---

## Month 1 — Seeing: frames → detections

| Wk | Topic | Hrs | Where | Milestone |
|---|---|---|---|---|
| [1](curriculum/week-01-frame-io.md) | Frame I/O & the loop | 6 | Mac | Copy a video frame-by-frame through your own loop |
| [2](curriculum/week-02-detection.md) | Object detection & the Detector seam | 7 | Mac | Print every detection in a clip |
| [3](curriculum/week-03-annotation-sidecar.md) | Annotation & the sidecar | 6 | Mac | `clip.annotated.mp4` + `clip.detections.jsonl` |
| [4](curriculum/week-04-sliced-inference.md) | Sliced inference (SAHI) | 7 | Mac | Find small objects in a 4K clip that plain inference misses |

## Month 2 — Remembering: detections → identity

| Wk | Topic | Hrs | Where | Milestone |
|---|---|---|---|---|
| [5](curriculum/week-05-tracking-by-hand.md) | Tracking by hand (IoU + greedy) | 7 | Mac | Your own tracker holds an id across 100 frames |
| [6](curriculum/week-06-bytetrack.md) | ByteTrack & `model.track()` | 6 | Mac | `--track` with stable `#id` labels + trails |
| [7](curriculum/week-07-zoom-slots.md) | Identity-aware rendering | 6 | Mac | Zoom panels pinned to ids, no reflow |
| [8](curriculum/week-08-live-mode.md) | Live mode & the source/sink seams | 7 | Mac | `--source 0` live webcam preview |

## Month 3 — Acting: identity → motion

| Wk | Topic | Hrs | Where | Milestone |
|---|---|---|---|---|
| [9](curriculum/week-09-servos.md) | Servos & the Pi-side split | 5 + 2 `[Pi]` | Mac→Pi | Teleop harness moves the real turret; limits measured |
| [10](curriculum/week-10-wire-listener.md) | The command plane (UDP) | 4 + 2 `[Pi]` | Mac→Pi | Drive the real servos from the Mac over UDP |
| [11](curriculum/week-11-visual-servoing.md) | Visual servoing (P → PID) | 5 + 3 `[Pi]` | Mac→Pi | The turret follows you, without oscillating |
| [12](curriculum/week-12-sentry-integration.md) | Sentry mode & integration | 4 + 3 `[Pi]` | Mac→Pi | Closed loop: it sweeps, finds you, locks on |

---

## What got trimmed for a 5–8 hr week

Three things, so you know what you're *not* doing and can add them back later:

- **Week 5: no Kalman filter from scratch.** You'll build IoU + greedy assignment, which is
  where the real insight is (detection is stateless; tracking is state). The Kalman motion
  model is read-and-understand, with a 30-line demo to run — not build. Add it in the
  stretch goal if the week goes fast.
- **Week 7 is trimmed to the slot state machine.** The cv2 raster details of `zoom.py`
  (EMA smoothing, label scaling, border drawing) are given to you. The lesson is the
  fixed-slot ownership machine, not the pixel arithmetic.
- **Week 12 hands you `streamer.py`'s HTTP boilerplate.** You implement `_encode_part` and
  the capture Protocol; the `BaseHTTPRequestHandler` scaffolding is provided.

## Stretch goals (if a week runs short)

- Add the Kalman motion model to your week-5 tracker and measure the ID-switch reduction.
- Write a second `Detector` backend (RF-DETR) — the payoff of the week-2 Protocol, proved.
- Export to ONNX and compare FPS against the `.pt` path.
- Sign the UDP datagrams with HMAC (week 10's security note names this as the real fix).

## Pacing

An evening week is ~3 sessions of ~2 hrs. Each week doc splits the work into sessions on
that assumption. If you fall behind: **skip the stretch goals, never the ADR.** The writing
is where the understanding gets consolidated.
