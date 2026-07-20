# Pan-tilt tracking turret: a physical actuator behind a new Frame-Sink-shaped seam

We add a **physical body** to the pipeline: a pan-tilt turret that rotates to keep a [Track]
centred in frame — the visual-servoing ("eye-in-hand") problem. The full design and phased
build-and-learn roadmap live in `docs/superpowers/specs/2026-07-04-pan-tilt-tracking-turret-design.md`;
this ADR records the load-bearing architectural choices.

The turret is a **Raspberry Pi 5 + Waveshare Pan-Tilt HAT + USB camera**. Detection stays where
it already runs — **the host (Mac) is the brain; the Pi is only the actuator**. The camera is
mounted *on* the moving platform, so this is a genuine closed feedback loop, not open-loop aiming.

## The seam (the load-bearing decision)

The turret enters the pipeline as **an [Actuator Sink]** — a [Frame Sink] variant (ADR-0010) that,
instead of drawing to a window or file, consumes the frame's [Track]s and emits an aim command.
The existing `detect → track → annotate` core is untouched; the loop still just hands each
annotated frame to a sink. Because sinks compose, aiming the turret while also showing a [Live
Preview] is two sinks, not a new code path.

Inside the sink, three small units carry the work — each a **pure function**, testable on the host
with no hardware:

- **[Target Selector]** — picks which [Track] to follow. **Policy: lock-first-id.**
- **[Aim Controller]** — maps the target's pixel offset from frame centre to a servo move.
  Proportional first, PID once the P-only loop is seen to overshoot.
- The **Aim Command** it produces `(pan_delta, tilt_delta)` is shipped to the Pi's servo driver.

## Mac = brain, Pi = actuator (not detection-on-Pi)

Detection runs on the host, the Pi only moves servos and streams its camera up. This reuses the
existing [Detector]/[Tracker] code verbatim and keeps FPS high. The cost is a network **inside the
control loop**: video travels up (MJPEG for v1), an Aim Command travels down (a simple UDP/TCP
socket), adding ~50–200 ms of lag. That latency is precisely why an [Aim Controller] exists rather
than snapping the servo to the target — a naive snap oscillates.

## Target selection: lock-first-id

The [Target Selector] latches onto the **first stable [Track] `#id`** it sees and follows that id
until the [Track] is lost, then re-latches on the next. This is deterministic and jitter-free: the
turret never flip-flops between targets frame to frame, and the policy composes cleanly with
ByteTrack's own id persistence — a briefly-missing target keeps its id (and the lock) across the
tracker's lost-track buffer (ADR-0012).

## Considered options

- **Detection on the Pi** (Pi = brain *and* body) — rejected for v1: the Pi 5 forces a smaller /
  quantised model and lower FPS, and would fork the detection path off the host code. Mac-as-brain
  reuses everything. Reconsider only if untethering from the host becomes a goal.
- **Camera fixed, turret aims into a static scene** — rejected: it dodges the feedback loop but is
  not "the turret sees through its own aim". The camera-on-platform loop is the point.
- **Richer target policies now** (largest box / nearest-centre / operator pick) — deferred:
  lock-first-id is the simplest thing that tracks one object well; the [Target Selector] seam lets
  us swap the policy later without touching the loop or the controller.
- **Low-latency transport now** (WebRTC / gRPC / GStreamer) — rejected for v1: weeks of yak-shaving
  for latency we haven't yet measured as a problem. MJPEG + a plain socket first; optimise only if
  the loop proves unstable.
- **GPIO PWM for the servos** — moot: the HAT drives its servos via a PCA9685 over **I²C**, which
  sidesteps the Pi 5 `RPi.GPIO` PWM breakage entirely.

## Consequences

- **A network sits inside the control loop.** Loop stability, not raw accuracy, is the design
  driver — hence the deliberate P → PID progression and a deadzone around frame centre.
- **The turret is opt-in and composable.** It is one more [Frame Sink]; runs with or without a
  [Live Preview] or recorder, and nothing about Offline mode changes.
- **New host-side domain vocabulary** — [Actuator Sink], [Target Selector], [Aim Controller] — is
  added to `CONTEXT.md`. The Pi-side units (servo driver, frame streamer, command listener) live in
  the turret's own package/repo, outside this glossary.
- **Software must clamp servo angles.** Mechanical limits are enforced in code (Pi side); a stray
  command must never drive a servo into a stall. First thing built (roadmap Phase 1).
- **Honest failure mode: lost target.** When the locked [Track] disappears and none re-latches, the
  turret holds position (v1); an active search sweep is deferred (roadmap Phase 5).
