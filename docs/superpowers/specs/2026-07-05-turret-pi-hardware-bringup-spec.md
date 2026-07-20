# Turret Pi — Hardware Bring-up Spec (ServoDriver · Frame Streamer · main)

**Date:** 2026-07-05
**Status:** Draft — ready for review, then implementation
**Depends on:** ADR-0013, `docs/superpowers/specs/2026-07-04-pan-tilt-tracking-turret-design.md`
**Scope:** the three remaining Pi-side (`turret_pi`) components. Everything else — the whole Mac
side and the Pi command plane (`wire.decode`, `ServoAngles`/`clamp_angles`, `listener.run_listener`) —
is built and tested.

## Purpose

Fill in the only code that cannot exist without the Raspberry Pi 5 + Waveshare Pan-Tilt HAT in
hand, so the turret runs end-to-end (Phases 1–3 of the roadmap). Three files:

| # | File | Role | Phase |
|---|---|---|---|
| 1 | `turret/turret_pi/servo.py` → `ServoDriver` | The hardware muscle: relative Aim Command → clamped absolute pose → PCA9685 over I²C | 1 |
| 2 | `turret/turret_pi/streamer.py` → `run_streamer` | The eye: capture the USB camera, serve MJPEG over HTTP so the Mac ingests it | 2 |
| 3 | `turret/turret_pi/main.py` → `main` | The entrypoint: build the driver, start the streamer thread, run the listener | 2 |

Non-goals: no changes to the Mac side (it is done); no new domain vocabulary in `CONTEXT.md`
(Pi-side units live outside the glossary per ADR-0013); no low-latency transport (Phase 5).

## What these three plug into (already built — do not re-open)

- **`Servo` Protocol** (`turret_pi/listener.py`): the listener needs exactly one method,
  `apply_delta(pan_delta: float, tilt_delta: float) -> None`. `ServoDriver` is its real
  implementation; the listener never imports `ServoDriver` directly.
- **`run_listener(servo, port=None, *, host, sock, allowed_source, should_continue, recv_timeout)`**:
  the blocking UDP loop. `main` calls it with a real `ServoDriver` and the configured port.
- **`ServoAngles(pan_deg, tilt_deg)` + `clamp_angles(...)`** (`turret_pi/servo.py`, pure): the pose
  type and the mechanical-limit clamp. Limits today: pan `0–180°`, tilt `0–180°`. `ServoDriver`
  holds a `ServoAngles` as its current pose and clamps every move through `clamp_angles`.
- **Wire contract**: one JSON datagram `{"pan_delta": <deg>, "tilt_delta": <deg>, "seq": <int>}`,
  UDP, default port 9000; `pan_delta` +right, `tilt_delta` +up (image-relative, ADR-0013).
- **Mac video ingest**: `object_tracker.sources` already treats an `http://` source as a stream
  (`_STREAM_SCHEMES`) and opens it via `cv2.VideoCapture`. So the streamer only has to emit a
  standard `multipart/x-mixed-replace` MJPEG stream OpenCV can open — **zero new Mac code**.

## Decisions to lock

### D1 — HAT SDK (the one true open item from the design spec)

`ServoDriver` needs a library to speak I²C to the PCA9685. Recommended and alternative:

| Option | Call surface | Verdict |
|---|---|---|
| **Adafruit CircuitPython — `adafruit-circuitpython-servokit`** (pulls in `adafruit-blinka` + `adafruit-circuitpython-pca9685` + `adafruit-motor`) | `kit = ServoKit(channels=16); kit.servo[0].angle = 90.0` | **Recommended.** Speaks in **degrees** directly — a near-perfect match for `ServoAngles`, so the degrees→PWM calibration is mostly `actuation_range` + `set_pulse_width_range(min_us, max_us)` rather than hand-rolled duty-cycle math. Best-documented; huge community. |
| Waveshare's own demo lib (raw `PCA9685.py` from the HAT wiki) | `pwm.setServoPulse(channel, us)` | Fallback. Lower-level (microseconds/duty), example-grade code, thinner docs. Choose only if Blinka/ServoKit misbehaves on the Pi 5. |

Both isolate behind `ServoDriver`, so the pick touches **one file**. This spec assumes ServoKit;
a Waveshare swap changes only `ServoDriver.__init__` and the write in `apply_delta`.

### D2 — Pin assignment
PCA9685 channels: **pan = channel 0, tilt = channel 1** (adjust to the HAT's silkscreen during
Phase 1 teleop). Named as constants, not magic numbers.

### D3 — Calibration is a Phase-1 empirical step, not guessable
Per-servo pulse range (`min_us`/`max_us`, typically ~500–2500 µs) and the **sign** of each axis
(does `+pan_delta` increase or decrease `pan_deg`? does `+tilt_delta` tilt up or down?) are
measured with the teleop harness (below), then frozen as constants. The sign flip is the classic
first bug (ADR-0013 Risks); the teleop script exists to nail it before the loop is closed.

### D4 — Ports & config
`--port` (UDP command, default `9000`) and `--stream-port` (HTTP MJPEG, default `8000`),
`--camera-index` (default `0`), `--host`, `--allowed-source` (optional, forwarded to the
listener). Parsed in `main` via `argparse`; no env-var layer for v1 (YAGNI).

### D5 — Threading model
Streamer runs on a **daemon thread**; the listener owns the **main thread** (its blocking
`recvfrom` loop is the process's heartbeat). Rationale: the listener is the safety-critical path
(it moves motors); keeping it on the main thread means `Ctrl-C`/`SIGTERM` interrupts it directly
and `main` can drive a clean shutdown.

---

## Component 1 — `ServoDriver`

### Responsibility
Turn a stream of **relative** Aim Command nudges into **absolute, clamped** servo positions and
write them to the PCA9685 over I²C. The adapter between our domain (`apply_delta`) and the vendor
SDK (`kit.servo[n].angle = ...`). It owns: the current pose, the degrees→hardware calibration, the
sign mapping, centering on startup.

### Interface
```python
# turret/turret_pi/servo.py  (extends the existing pure ServoAngles/clamp_angles)

PAN_CHANNEL = 0
TILT_CHANNEL = 1
CENTER = ServoAngles(pan_deg=90.0, tilt_deg=90.0)   # mid-range on both axes
# Per-servo calibration (measured in Phase 1, then frozen):
SERVO_MIN_US = 500
SERVO_MAX_US = 2500
PAN_SIGN = +1.0    # +pan_delta (target right) → which way pan_deg moves; flip if reversed
TILT_SIGN = +1.0   # +tilt_delta (target up)  → which way tilt_deg moves; flip if reversed

class ServoDriver:
    """Real I²C driver for the Waveshare Pan-Tilt HAT (PCA9685). Implements the Servo Protocol
    the listener depends on. The only hardware-bound unit in turret_pi."""

    def __init__(self, kit=None, center: ServoAngles = CENTER) -> None:
        """Open the HAT (ServoKit) unless one is injected (test seam), set each channel's pulse
        range, and move to `center`. `kit=None` → construct the real ServoKit here."""

    def apply_delta(self, pan_delta: float, tilt_delta: float) -> None:
        """Accumulate the nudge onto the current pose, clamp to mechanical limits, write both
        channels. Never raises on a large delta — clamp makes it safe."""

    @property
    def current(self) -> ServoAngles:
        """Where the turret is pointing now (post-clamp)."""
```

### Behavior (`apply_delta`)
1. `target = ServoAngles(current.pan_deg + PAN_SIGN*pan_delta, current.tilt_deg + TILT_SIGN*tilt_delta)`
2. `safe = clamp_angles(target)`  ← reuses the built, tested pure function
3. Write: `kit.servo[PAN_CHANNEL].angle = safe.pan_deg`, `kit.servo[TILT_CHANNEL].angle = safe.tilt_deg`
4. `self._current = safe`

Immutability: `_current` is replaced with a new `ServoAngles`, never mutated in place (repo style).

### Testing (Mac, no hardware)
`ServoKit` is injectable, so `ServoDriver` is unit-testable with a **fake kit** (a stub exposing
`servo[0].angle`/`servo[1].angle` as recordable attributes), mirroring the `FakeServo`/fake-kit
pattern already used for the listener. Cover:
- a nudge accumulates onto the pose and writes both channels;
- a delta past a limit is **clamped** (never writes an out-of-range angle);
- successive nudges accumulate (relative, not absolute);
- `PAN_SIGN`/`TILT_SIGN` reverse the written direction;
- startup centers both channels.

The real `ServoKit` import must be **lazy / guarded** (inside `__init__`, or import-guarded) so the
module imports on the Mac for tests without `adafruit-blinka` installed.

### Risks
- **Sign errors** (wrong direction) — caught by the Phase-1 teleop harness before the loop closes.
- **Angle→pulse miscalibration** — servo buzzes/strains at the ends; fix `SERVO_MIN/MAX_US`.
- **Stall on power sag** — see the power note; unrelated to this code but presents as "servo twitch."

---

## Component 2 — `run_streamer`

### Responsibility
Capture the USB camera on the Pi and serve its frames as MJPEG over HTTP, so the Mac's existing
`CameraSource` opens it as a plain stream URL.

### Interface
```python
# turret/turret_pi/streamer.py

def run_streamer(
    camera_index: int = 0,
    port: int = 8000,
    *,
    path: str = "/stream.mjpg",
    should_continue: Callable[[], bool] = lambda: True,
) -> None:
    """Blocking: capture `camera_index` (OpenCV), MJPEG-encode each frame, serve
    `multipart/x-mixed-replace; boundary=frame` at `http://<pi>:<port><path>`. Runs until
    `should_continue()` is False (main runs it on a daemon thread)."""
```

### Behavior
- Open the camera with `cv2.VideoCapture(camera_index)`; raise a clear `RuntimeError` if it won't
  open (mirrors `CameraSource`'s open-failure message).
- Serve one endpoint via stdlib `http.server` (`ThreadingHTTPServer`): respond
  `Content-Type: multipart/x-mixed-replace; boundary=frame`, then loop: read a frame,
  `cv2.imencode(".jpg", frame)`, write the `--frame\r\nContent-Type: image/jpeg\r\n...` part.
- Stdlib HTTP + OpenCV only — no Flask/aiohttp (KISS; the Mac side is a `VideoCapture`, not a
  browser, so a minimal server suffices).

### Verification
Phase-2 standalone check **before** wiring into detection: open
`http://<pi-ip>:8000/stream.mjpg` in VLC/a browser and see live video; then
`uv run track --source http://<pi-ip>:8000/stream.mjpg --track` on the Mac and see `#id` boxes on
the turret's feed. This is also where the **real end-to-end latency** gets measured (the number
ADR-0013's control design hinges on).

### Testing
Camera + sockets are hardware/IO, so unit tests are thin: factor the **frame→MJPEG-part
byte-framing** into a tiny pure helper (`_encode_part(jpeg_bytes) -> bytes`) and unit-test that on
the Mac. The capture/serve loop is verified live (Phase-2 check above), consistent with the design
spec's "frame streamer verified standalone" testing strategy.

### Risks
- **USB bandwidth / cable on a moving platform** — leave slack (ADR-0013 cable-management note).
- **Encoding CPU on the Pi** — MJPEG is cheap; if FPS sags, drop resolution before optimizing.

---

## Component 3 — `main.py`

### Responsibility
The `turret` entrypoint already declared in `turret/pyproject.toml`
(`turret = "turret_pi.main:main"` — currently dangling, no `main.py`). Wire the three units and
own process lifecycle.

### Interface & behavior
```python
# turret/turret_pi/main.py

def main(argv: list[str] | None = None) -> int:
    """Parse args (D4) → build ServoDriver → start run_streamer on a daemon thread →
    run_listener(driver, port, host=..., allowed_source=...) on the main thread until
    SIGINT/SIGTERM. Clean shutdown: stop the loops, recenter the servos, return 0."""
```
- **Startup order:** driver first (so a servo fault fails fast, before we advertise a stream),
  then streamer thread, then listener (blocks).
- **Shutdown:** a `threading.Event` backs `should_continue` for both loops; `SIGINT`/`SIGTERM`
  set it. On exit, recenter via `driver.apply_delta` back toward `CENTER` (leave the turret in a
  known safe pose), then return `0`. `KeyboardInterrupt` handled the same way.
- **Deploy:** documented to run under **systemd** (`ExecStart=… turret …`, `Restart=on-failure`).
  systemd restart is also what makes the listener's session-gap recovery matter (seq resets to 1
  on restart — already handled).

### Testing
`main`'s wiring is integration-shaped; keep logic testable by having it call small, already-tested
units. A light test can inject a fake driver + a `should_continue` that flips false after one tick
to assert startup/shutdown order without real hardware.

---

## Dependencies to add — `turret/pyproject.toml`

Currently `dependencies = []`. Add (ServoKit path):
```toml
dependencies = [
    "opencv-python",                        # camera capture + MJPEG encode (streamer)
    "adafruit-circuitpython-servokit",      # PCA9685 over I²C in degrees (ServoDriver)
]
```
These are **Pi-only** and stay out of the Mac's `object_tracker` graph (the whole point of the
separate `turret-pi` package — ADR-0013). `adafruit-blinka` comes in transitively and only imports
cleanly on the Pi, which is why the `ServoKit` import must be lazy/guarded for Mac-side tests.

## Testing strategy (summary)

| Unit | Mac-testable (no HW) | Needs the rig |
|---|---|---|
| `ServoDriver` (accumulate/clamp/sign/center) | ✅ fake kit | pulse calibration, real motion |
| `run_streamer` byte-framing helper | ✅ pure helper | capture + serve + latency |
| `main` wiring | ✅ fake driver + stop-after-one-tick | full end-to-end |

Pure-first, hardware-last — the same discipline the rest of the turret followed.

## Build sequence

1. **`ServoDriver`** + fake-kit tests (Mac) → then Phase-1 **teleop script** on the Pi to calibrate
   `SERVO_MIN/MAX_US`, `PAN_SIGN`, `TILT_SIGN`, pin channels. *Done when a keyboard aims the turret.*
2. **`run_streamer`** + framing test → Phase-2 live check (VLC, then `uv run track --source http://…`).
   *Done when the Mac shows `#id` boxes on the turret feed; latency measured.*
3. **`main.py`** wiring + shutdown → `turret` entrypoint runs → run the Mac tracker with
   `--turret <pi-ip>:9000`. *Done when the turret follows a target (Phase 3, jittery P — expected).*
4. Tune `--turret-kp/-ki/-kd` (Phase 4) once the P loop is seen to overshoot.

## Open items

- **Final SDK pick** (D1) — recommend ServoKit; confirm it initialises on the Pi 5 in Phase 0/1.
- **Servo pulse range** per the actual servos (D3) — empirical, Phase 1.
- **HMAC-signed datagrams** — deferred, but the prerequisite before this drives anything dangerous
  (ADR-0013 trust model); note it here so it is not forgotten.
