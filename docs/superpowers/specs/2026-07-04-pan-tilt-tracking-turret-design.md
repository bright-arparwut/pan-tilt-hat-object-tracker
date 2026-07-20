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
| Target selection | **Lock-first-id** | Follow the first stable ByteTrack `#id` seen; ignore the rest until it is lost. Simplest deterministic policy; no per-frame "best target" flip-flopping (see ADR-0013). |

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
  one to follow. **Policy: lock-first-id** — latch onto the first stable `#id` seen and keep
  following that id until it is lost (then re-latch on the next). Pure, testable.
- **`actuator sink` (Mac)** — Glue: pulls the selected target from the pipeline, runs the
  controller, ships the command down. Mirrors the existing `sinks.py` shape.

## Code architecture (Phases 1–4)

Concrete file-level blueprint turning the component design above into buildable modules.
Produced via `ecc:code-architect` reviewing this doc, ADR-0013, `CONTEXT.md`, and the existing
`sinks.py` / `pipeline.py` / `config.py` / `tracking.py` / `sources.py`. Covers Phases 1–4 only
(Phase 0 Pi setup and Phase 5 stretch goals are out of scope here).

### Design decisions

- **Pi-side code lives in a new top-level `turret/` directory with its own `pyproject.toml`**,
  importable as `turret_pi` — not inside `object_tracker/`. Different runtime host (ARM/Raspbian
  vs. Mac), disjoint dependency graphs (I²C/HAT SDK + camera capture on the Pi; `ultralytics`/
  `torch` stay Mac-only), and a different deploy lifecycle (`python -m turret_pi.main` under
  systemd, not `uv run track`). One git repo, two independently-installable packages.
- **Mac-side code is a new `object_tracker/turret_sink/` subpackage**, mirroring the existing
  `object_tracker/detection/` subpackage shape. Named `turret_sink`, not `turret`, so it doesn't
  collide (in a reader's head) with the top-level Pi `turret/` folder.
- **`FrameSink.show()` gains one optional parameter, `tracks`, defaulting to `None`.** The one
  required change to the existing, tested `FrameSink` Protocol — see "The FrameSink seam" below.
- **`pipeline.run()`'s own parameter list is unchanged.** The Actuator Sink is assembled entirely
  in `cli.py` (parse `--turret`, build `ActuatorSink`, fold into `CompositeSink`), exactly like
  `--record` does today for `VideoFileSink`. `pipeline.py`'s only diff is threading the
  already-computed `confirmed` Detections into the existing `sink.show(...)` call.
- **Target Selector and Aim Controller are pure functions, not classes** —  `select_target(...)`
  and `step(...)` take and return immutable state (`AimControllerState`), threaded by a thin
  stateful wrapper (`ActuatorSink`) — the same pure-step-wrapped-in-a-stateful-manager shape
  `ZoomSlots` already uses in `zoom.py`.
- **P and PID are the same function** (`aim_controller.step`), differing only by which gains
  (`ki`, `kd`) are nonzero — Phase 3→4 is a gain-tuning change, not a rewrite.
- **Wire protocol: one JSON object per UDP datagram**, e.g.
  `{"pan_delta": -2.3, "tilt_delta": 0.8, "seq": 1042}`. UDP because the control loop wants
  "freshest command wins," not head-of-line-blocked delivery of a stale command; JSON because
  it's debuggable with `netcat` and matches this repo's existing JSONL sidecar convention
  (`sidecar.py`). No shared code module between Mac and Pi (separate deployables/deps per
  ADR-0013) — each side owns a tiny, independently-tested encode/decode of the same documented
  shape.
- **Command channel is fire-and-forget, no ack/retry.** A dropped Aim Command is superseded by
  the next one ~30–60ms later; retrying a stale command is worse than dropping it.

### Files to create

| File | Purpose | Priority |
|---|---|---|
| `object_tracker/turret_sink/__init__.py` | Re-exports: `AimGains`, `AimCommand`, `AimControllerState`, `step`, `select_target`, `AimTransport`, `UdpAimTransport`, `ActuatorSink` | P1 |
| `object_tracker/turret_sink/target_selector.py` | `select_target(present_ids, prior_lock) -> locked_id \| None` — pure lock-first-id policy | P1 |
| `object_tracker/turret_sink/aim_controller.py` | `AimControllerState`, `AimCommand`, `step(error_px, gains, prev_state, dt) -> (AimCommand, AimControllerState)` — pure P/PID | P1 |
| `object_tracker/turret_sink/wire.py` | `encode(command, seq) -> bytes` — Mac-side half of the UDP JSON wire format | P2 |
| `object_tracker/turret_sink/transport.py` | `AimTransport` Protocol + `UdpAimTransport` — the sole Mac-side network I/O | P2 |
| `object_tracker/turret_sink/actuator_sink.py` | `ActuatorSink` — the `FrameSink` implementation; glue only | P2 |
| `turret/pyproject.toml` | Separate installable package (`turret-pi`); own deps (camera capture, HAT/PCA9685 SDK) | P1 |
| `turret/turret_pi/__init__.py` | Package marker | P1 |
| `turret/turret_pi/servo.py` | `ServoAngles`, `clamp_angles` (pure), `ServoDriver` (I²C/HAT I/O) — Phase 1 | P1 |
| `turret/turret_pi/wire.py` | `decode(payload) -> (pan_delta, tilt_delta, seq)` — Pi-side half of the wire format | P2 |
| `turret/turret_pi/streamer.py` | `run_streamer(camera_index, port)` — MJPEG `multipart/x-mixed-replace` HTTP server | P2 |
| `turret/turret_pi/listener.py` | `run_listener(servo, port)` — UDP receive loop, drops stale/malformed datagrams, calls `servo.apply_delta` | P2/P3 |
| `turret/turret_pi/main.py` | Entrypoint: builds `ServoDriver`, starts streamer thread, runs listener | P2 |
| `tests/test_target_selector.py` | Table-driven pure-function tests | P3 |
| `tests/test_aim_controller.py` | Pure-function tests incl. deadzone, clamp, P-vs-PID gain behaviour | P3 |
| `tests/test_actuator_sink.py` | `ActuatorSink` with a fake `AimTransport` double (mirrors `FakeSink` in `test_sinks.py`) | P3 |
| `turret/tests/test_servo.py` | `clamp_angles` pure tests, no HAT attached | P3 |
| `turret/tests/test_wire.py` | `decode` pure tests incl. malformed-payload behaviour | P3 |

### Files to modify

| File | Changes | Priority |
|---|---|---|
| `object_tracker/sinks.py` | Widen `FrameSink.show` to `show(self, frame: np.ndarray, tracks: sv.Detections \| None = None) -> bool`. `VideoFileSink`/`WindowSink` gain the param and ignore it. `CompositeSink` gains the param and forwards it to every child: `sink.show(frame, tracks)`. | P1 |
| `object_tracker/pipeline.py` | Add `import supervision as sv`; add `tracks: sv.Detections \| None = None` before the branch, set `tracks = confirmed` in the track branch, change the call site to `sink.show(annotated, tracks)`. No other loop logic changes. | P1 |
| `object_tracker/config.py` | Add `AimGains` (frozen: `kp`, `ki=0.0`, `kd=0.0`, `deadzone_px`, `max_delta_deg`) and `TurretConfig` (frozen: `host`, `port`, `gains: AimGains`), plus `DEFAULT_TURRET_KP/KI/KD/DEADZONE_PX/MAX_DELTA_DEG/PORT` constants — same section/placement as `TrackConfig`/`ZoomConfig`. | P1 |
| `object_tracker/cli.py` | Add `--turret HOST:PORT` + `--turret-kp/-ki/-kd/-deadzone-px/-max-deg` flags; a `_parse_turret_target(text) -> (host, port)` helper; extend `validation_error(...)` with `turret: bool = False` → `"--turret requires --track"`; a `_maybe_add_turret(sink, args, frame_wh) -> FrameSink` helper that builds `UdpAimTransport` + `ActuatorSink` and wraps into `CompositeSink`; enforce Live-only for `--turret` (mirrors the existing `--record` Live-only check). | P2 |
| `tests/test_sinks.py` | `FakeSink.show` gains `tracks=None`; add a test asserting `CompositeSink` forwards `tracks` to every child unchanged; existing single-arg `.show(frame)` calls keep working (default `None`). | P3 |
| `pyproject.toml` (repo root) | No new deps — Mac side uses only stdlib `socket`/`json` beyond what's already there. | P1 |

### The FrameSink seam (resolution)

`FrameSink.show` today is `show(self, frame: np.ndarray) -> bool`. The Actuator Sink needs the
frame's tracked boxes with ids, which `pipeline.run` already computes as `confirmed` inside its
`if rt is not None and tracking_detector is not None:` branch — it just never leaves that scope.

Two seams were considered:

1. **Widen `FrameSink.show` with an optional `tracks` param** (chosen). One call site in
   `pipeline.run` always passes `tracks` (the real `confirmed` under `--track`, `None`
   otherwise); every sink signature grows by one ignorable parameter. `pipeline.run`'s own
   parameter list and control flow do not change at all.
2. **A separate marker protocol** (`TrackSink.show_tracks(tracks)`) detected via `hasattr`/
   `isinstance` in the loop, called only from the track branch — rejected: it reintroduces a
   sink-type branch inside `pipeline.run`, which is exactly what `CONTEXT.md` says the loop
   must not have (it never knows it is aiming a motor). A single uniform `show(frame, tracks)`
   call keeps the loop sink-agnostic; each sink decides what to use.

Cost of option 1: `VideoFileSink`, `WindowSink`, `CompositeSink`, and the `FakeSink` test double
all gain a parameter they mostly ignore — a small, mechanical, one-time diff, not a new
abstraction. `CompositeSink` is the one non-trivial change: it must forward `tracks` to every
child so a `--record` + `--turret` run (window + file + actuator, all fanned out from one
`CompositeSink`) works without new call sites.

### Component signatures

```python
# object_tracker/turret_sink/target_selector.py
def select_target(present_ids: frozenset[int], prior_lock: int | None) -> int | None:
    """Pure: keep prior_lock if still present; else lock the smallest present id (ByteTrack
    ids are monotonic, so min(present) == first-seen — the same trick zoom.py's ZoomSlots
    already uses); empty present -> stay unlocked (v1 holds position, ADR-0013)."""

# object_tracker/turret_sink/aim_controller.py
@dataclass(frozen=True)
class AimCommand:
    pan_delta: float   # deg, +right
    tilt_delta: float  # deg, +up

@dataclass(frozen=True)
class AimControllerState:
    integral_x: float = 0.0
    integral_y: float = 0.0
    prev_error_x: float = 0.0
    prev_error_y: float = 0.0

def step(
    error_px: tuple[float, float],
    gains: AimGains,          # from object_tracker.config
    prev_state: AimControllerState,
    dt: float,
) -> tuple[AimCommand, AimControllerState]:
    """Pure P (ki=kd=0, Phase 3) / PID (Phase 4) — same function, different gains."""

# object_tracker/turret_sink/transport.py
class AimTransport(Protocol):
    def send(self, command: AimCommand) -> None: ...
    def close(self) -> None: ...

class UdpAimTransport:
    def __init__(self, host: str, port: int) -> None: ...
    def send(self, command: AimCommand) -> None: ...  # fire-and-forget, increments seq
    def close(self) -> None: ...

# object_tracker/turret_sink/actuator_sink.py
class ActuatorSink:
    def __init__(self, transport: AimTransport, gains: AimGains, frame_wh: tuple[int, int]) -> None: ...
    def show(self, frame: np.ndarray, tracks: sv.Detections | None = None) -> bool:
        """Never draws; always returns True (never asks the loop to stop). Uses
        tracking._present_centers(tracks) (already imported the same way in pipeline.py)
        to get {tracker_id: center}, threads select_target + step, sends via transport."""
    def close(self) -> None: ...  # closes the transport

# turret/turret_pi/servo.py
@dataclass(frozen=True)
class ServoAngles:
    pan_deg: float
    tilt_deg: float

def clamp_angles(angles: ServoAngles) -> ServoAngles: ...  # pure, hardware-free unit test

class ServoDriver:
    def __init__(self) -> None: ...       # opens I2C/HAT, centers
    def apply_delta(self, pan_delta: float, tilt_delta: float) -> None: ...  # relative nudge, clamped
    @property
    def current(self) -> ServoAngles: ...

# turret/turret_pi/wire.py
def decode(payload: bytes) -> tuple[float, float, int]: ...  # (pan_delta, tilt_delta, seq); raises on garbage

# turret/turret_pi/listener.py
def run_listener(servo: ServoDriver, port: int) -> None:
    """Blocking UDP loop: decode -> drop malformed/stale (seq <= last_seq) -> servo.apply_delta."""
```

### Data flow

**Phase 2 (eye→brain):** `turret_pi.streamer` captures the USB cam, MJPEG-encodes each frame,
serves it over HTTP. On the Mac, `--source http://<pi>:<port>/stream.mjpg` builds the existing
`CameraSource` **unchanged** — `sources.py`'s stream-scheme handling already accepts `http`, so
Phase 2 needs **zero new Mac-side ingest code**; the existing Live path detects/tracks it like
any other Live source.

**Phase 3–4 (close the loop):** each frame, `pipeline.run` computes `confirmed` (under
`--track`) and now passes it to `sink.show(annotated, confirmed)`. When the sink is a
`CompositeSink` containing an `ActuatorSink`, that sink: (1) turns `confirmed` into
`{tracker_id: center}` via the already-existing `tracking._present_centers`; (2)
`select_target` latches/keeps the followed id; (3) computes pixel error vs. frame center; (4)
`aim_controller.step` turns error + gains + prior state into an `AimCommand` + new state; (5)
`UdpAimTransport.send` JSON-encodes and fires a UDP datagram to the Pi. On the Pi,
`turret_pi.listener` decodes it, drops it if malformed or stale-by-`seq`, and calls
`ServoDriver.apply_delta`, which clamps to mechanical limits and writes the new angles over I²C
to the PCA9685. The camera being mounted on the same platform closes the loop: the next
captured frame reflects the servo's move.

### Build sequence

1. **Types/config** — `object_tracker/config.py`: `AimGains`, `TurretConfig`, defaults.
   `turret/turret_pi/servo.py`: `ServoAngles` + `clamp_angles` (pure, no hardware yet).
2. **Core logic (pure, Mac)** — `target_selector.py`, `aim_controller.py`, `wire.py` (encode) —
   fully unit-testable with zero hardware, per the testing strategy below.
3. **Core logic (Pi)** — `servo.py`'s `ServoDriver` (real I²C), `turret_pi/wire.py` (decode).
   Verified with the Phase 1 keyboard teleop harness, which exercises exactly `ServoDriver`.
4. **Integration layer** — `sinks.py` widen `FrameSink`; `pipeline.py` thread `tracks` through;
   `transport.py` + `actuator_sink.py` on the Mac; `streamer.py` + `listener.py` + `main.py` on
   the Pi.
5. **CLI/UI** — `cli.py`: `--turret` flags, validation, `_maybe_add_turret` wiring.
6. **Tests** — pure-function tests first (selector, controller, clamp, decode), then
   `ActuatorSink`/`CompositeSink`-forwarding tests with fake doubles, matching the existing
   `FakeSink` pattern in `tests/test_sinks.py`.

**Open item for Phase 1** (not answerable from the repo alone): the exact Waveshare Pan-Tilt HAT
Python SDK call surface (`adafruit-circuitpython-pca9685` vs. Waveshare's own demo library) —
`ServoDriver.__init__`/`apply_delta` bodies are sketched generically above and should be filled
in against whichever SDK the Phase 0/1 setup settles on; `clamp_angles` and the rest of this
blueprint are independent of that choice.

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
- **"Which target?"** — ByteTrack yields multiple `#id`s; resolved as **lock-first-id** (latch the
  first stable id, re-latch on loss), isolated in the `target selector` unit. Fancier policies
  (largest / nearest-center / operator pick) are deferred (ADR-0013).
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

Code architecture for Phases 1–4 is now blueprinted above (files, signatures, the `FrameSink`
seam resolution, build sequence). Turn it into a concrete implementation plan — starting with
Phase 0 (Pi foundations, not designed here) and Phase 1 (`turret/turret_pi/servo.py` +
`object_tracker/config.py`'s `AimGains`/`TurretConfig`) — via the writing-plans workflow, then
TDD each pure-function module (target selector → aim controller → wire → integration) per the
testing strategy above.
