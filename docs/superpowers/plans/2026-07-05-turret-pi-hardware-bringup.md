# Turret Pi Hardware Bring-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the three remaining Pi-side `turret_pi` components — the `ServoDriver` (I²C actuator), the MJPEG `run_streamer` (camera → HTTP), and the `main` entrypoint that wires them to the existing UDP listener — so the turret runs end-to-end.

**Architecture:** `turret_pi` is a standalone package (separate venv from `object_tracker`). The hardware-free half is already built and tested (`servo.ServoAngles`/`clamp_angles`, `wire.decode`, `listener.run_listener`, which depends only on a `Servo` Protocol). This plan adds the hardware-bound half behind test seams: the vendor SDK (`ServoKit`) is injected into `ServoDriver`, the camera/socket loop of `run_streamer` is verified live while its pure byte-framing is unit-tested, and `main`'s wiring is exercised with fakes for the driver/streamer/listener. Pure-first, hardware-last — the same discipline the rest of the turret followed.

**Tech Stack:** Python ≥3.10, pytest (via `uv`), stdlib `http.server` + OpenCV (streamer), Adafruit CircuitPython ServoKit → PCA9685 over I²C (driver), stdlib `argparse`/`signal`/`threading` (entrypoint).

## Global Constraints

- **Python floor:** `requires-python = ">=3.10"` (matches `turret/pyproject.toml`).
- **Test invocation:** all turret tests run from the `turret/` directory: `cd turret && uv run pytest`. Package imports are `from turret_pi.<module> import ...`.
- **Pi-only SDK stays out of the Mac import path:** the `adafruit_servokit` import MUST be lazy (inside `ServoDriver.__init__`), so every `turret_pi` module imports on the Mac for tests **without** `adafruit-blinka` installed. `opencv-python` is cross-platform and may be a top-level import.
- **Immutability (repo style):** `ServoDriver._current` is *replaced* with a new `ServoAngles`, never mutated in place. Reuse the existing pure `clamp_angles`; never re-implement clamping.
- **Named constants, not magic numbers:** channels, center, pulse range, and axis signs are module-level constants (D2/D3 of the spec).
- **Wire contract is frozen:** one JSON UDP datagram `{"pan_delta", "tilt_delta", "seq"}`, `pan_delta` +right, `tilt_delta` +up, default command port `9000`, default stream port `8000` (D4).
- **KISS/YAGNI:** stdlib `http.server` only (no Flask/aiohttp); `argparse` only (no env-var layer for v1).
- **Do not touch the Mac side** (`object_tracker`) — it already ingests an `http://` source as a stream via `CameraSource`.

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `turret/turret_pi/servo.py` | Modify (append) | Add `ServoDriver` + calibration constants below the existing pure `ServoAngles`/`clamp_angles`. |
| `turret/turret_pi/teleop.py` | Create | Phase-1 keyboard calibration harness: pure `key_to_delta` (tested) + interactive `run_teleop` (live on the Pi). |
| `turret/turret_pi/streamer.py` | Create | `run_streamer` (capture → MJPEG over HTTP) + pure `_encode_part` byte-framing helper + `_open_camera`. |
| `turret/turret_pi/main.py` | Create | `main`/`run_turret`/`_parse_args`: build driver → start streamer thread → run listener → recenter on exit. |
| `turret/pyproject.toml` | Modify | Add `opencv-python` (base) and the Pi-only Adafruit stack (optional `hardware` extra). |
| `turret/tests/test_servo.py` | Modify (append) | Fake-kit `ServoDriver` tests below the existing clamp tests. |
| `turret/tests/test_teleop.py` | Create | `key_to_delta` mapping tests. |
| `turret/tests/test_streamer.py` | Create | `_encode_part` byte-exactness + `_open_camera` failure. |
| `turret/tests/test_main.py` | Create | `_parse_args` defaults/overrides + `run_turret` wiring order + recenter-on-exit. |

### Planner decisions (deviations from the spec — flagged for the reviewer)

1. **`recenter()` method instead of recenter-via-`apply_delta`.** Spec §main line 213 says shutdown recenters "via `driver.apply_delta` back toward `CENTER`". That is sign-fragile: with a flipped `PAN_SIGN`/`TILT_SIGN`, a relative delta recenters the *wrong* direction. This plan adds `ServoDriver.recenter()` that writes `CENTER` **absolutely** (angle 90/90 is the mechanical center regardless of delta sign), reusing the same private write path as startup centering. Correct and DRY.
2. **Pi-only deps live in an optional `hardware` extra, not base `dependencies`.** Spec §"Dependencies to add" lists both in `dependencies`. But spec §ServoDriver-Testing requires the module to "import on the Mac for tests **without `adafruit-blinka` installed**" — impossible if `adafruit-blinka` is a base dep that `cd turret && uv sync` installs. Resolution: `opencv-python` (cross-platform) in base `dependencies`; `adafruit-circuitpython-servokit` in `[project.optional-dependencies] hardware`, installed on the Pi with `uv sync --extra hardware`. The lazy import means Mac tests pass whether or not the extra is present.
3. **`teleop.py` is included** though the spec's scope *table* lists only three files. The spec's build sequence (step 1), D3, and Risks all make the teleop harness load-bearing for calibrating `PAN_SIGN`/`TILT_SIGN`/pulse range ("not guessable"). It is Task 2. A reviewer who considers bring-up tooling out of scope can drop it without affecting the other tasks.

---

### Task 1: ServoDriver + calibration constants

**Files:**
- Modify: `turret/turret_pi/servo.py` (append below `clamp_angles`)
- Modify: `turret/pyproject.toml` (add the optional `hardware` extra)
- Test: `turret/tests/test_servo.py` (append below the clamp tests)

**Interfaces:**
- Consumes (already built): `ServoAngles(pan_deg: float, tilt_deg: float)`, `clamp_angles(angles: ServoAngles) -> ServoAngles` — same module.
- Produces (later tasks rely on these exact names):
  - Constants: `PAN_CHANNEL=0`, `TILT_CHANNEL=1`, `CENTER=ServoAngles(90.0, 90.0)`, `SERVO_MIN_US=500`, `SERVO_MAX_US=2500`, `SERVO_ACTUATION_RANGE_DEG=180.0`, `PAN_SIGN=+1.0`, `TILT_SIGN=+1.0`.
  - `class ServoDriver` with `__init__(self, kit=None, center: ServoAngles = CENTER)`, `apply_delta(self, pan_delta: float, tilt_delta: float) -> None`, `recenter(self) -> None`, and property `current -> ServoAngles`. Satisfies the listener's `Servo` Protocol.

- [ ] **Step 1: Add the fake kit + first failing test**

Append to `turret/tests/test_servo.py`:

```python
from turret_pi.servo import (
    CENTER,
    SERVO_ACTUATION_RANGE_DEG,
    SERVO_MAX_US,
    SERVO_MIN_US,
    ServoDriver,
)


class _FakeChannel:
    """One PCA9685 channel: records the last angle written and the calibration applied."""

    def __init__(self) -> None:
        self.angle: float | None = None
        self.actuation_range: float | None = None
        self.pulse_range: tuple[int, int] | None = None

    def set_pulse_width_range(self, min_us: int, max_us: int) -> None:
        self.pulse_range = (min_us, max_us)


class FakeKit:
    """Stand-in for adafruit ServoKit: `servo[ch]` yields a recordable channel (no HAT)."""

    def __init__(self) -> None:
        self.servo = {0: _FakeChannel(), 1: _FakeChannel()}


def test_startup_centers_both_channels():
    kit = FakeKit()
    driver = ServoDriver(kit=kit)
    assert kit.servo[0].angle == 90.0
    assert kit.servo[1].angle == 90.0
    assert driver.current == CENTER
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd turret && uv run pytest tests/test_servo.py::test_startup_centers_both_channels -v`
Expected: FAIL — `ImportError: cannot import name 'ServoDriver' from 'turret_pi.servo'`.

- [ ] **Step 3: Implement `ServoDriver`**

Append to `turret/turret_pi/servo.py`:

```python
# --- Real I²C driver (ADR-0013 Phase 1) --------------------------------------------------
# The hardware-bound half: turns relative Aim Command nudges into absolute, clamped servo
# positions and writes them to the PCA9685. The only hardware-coupled unit in turret_pi.

PAN_CHANNEL = 0
TILT_CHANNEL = 1
CENTER = ServoAngles(pan_deg=90.0, tilt_deg=90.0)  # mid-range on both axes

# Per-servo calibration — measured with the Phase-1 teleop harness, then frozen (spec D3).
SERVO_MIN_US = 500
SERVO_MAX_US = 2500
SERVO_ACTUATION_RANGE_DEG = 180.0
PAN_SIGN = +1.0   # +pan_delta (target right) -> which way pan_deg moves; flip if reversed
TILT_SIGN = +1.0  # +tilt_delta (target up)   -> which way tilt_deg moves; flip if reversed


class ServoDriver:
    """Real I²C driver for the Waveshare Pan-Tilt HAT (PCA9685). Implements the ``Servo``
    Protocol the listener depends on. ``kit`` is injectable so the driver is unit-testable
    with a fake kit on the Mac; ``kit=None`` constructs the real ServoKit (lazy import)."""

    def __init__(self, kit=None, center: ServoAngles = CENTER) -> None:
        if kit is None:
            # Lazy/Pi-only: keeps every turret_pi module importable on the Mac for tests
            # without adafruit-blinka installed (spec §Testing, Global Constraints).
            from adafruit_servokit import ServoKit

            kit = ServoKit(channels=16)
        self._kit = kit
        self._center = center
        for channel in (PAN_CHANNEL, TILT_CHANNEL):
            servo = kit.servo[channel]
            servo.actuation_range = SERVO_ACTUATION_RANGE_DEG
            servo.set_pulse_width_range(SERVO_MIN_US, SERVO_MAX_US)
        self._write(center)  # sets self._current and moves the HAT to center on startup

    def _write(self, angles: ServoAngles) -> None:
        """Write an absolute pose to both channels and record it (single write path)."""
        self._kit.servo[PAN_CHANNEL].angle = angles.pan_deg
        self._kit.servo[TILT_CHANNEL].angle = angles.tilt_deg
        self._current = angles  # replaced, never mutated (repo immutability style)

    def apply_delta(self, pan_delta: float, tilt_delta: float) -> None:
        """Accumulate a relative nudge onto the current pose, clamp to mechanical limits,
        write both channels. Never raises on a large delta — clamp makes it safe."""
        target = ServoAngles(
            pan_deg=self._current.pan_deg + PAN_SIGN * pan_delta,
            tilt_deg=self._current.tilt_deg + TILT_SIGN * tilt_delta,
        )
        self._write(clamp_angles(target))

    def recenter(self) -> None:
        """Return to the mechanical center (absolute write; sign-independent). Called on
        shutdown to leave the turret in a known safe pose."""
        self._write(self._center)

    @property
    def current(self) -> ServoAngles:
        """Where the turret is pointing now (post-clamp)."""
        return self._current
```

- [ ] **Step 4: Run the test — it passes**

Run: `cd turret && uv run pytest tests/test_servo.py::test_startup_centers_both_channels -v`
Expected: PASS.

- [ ] **Step 5: Add the remaining behavior tests**

Append to `turret/tests/test_servo.py`:

```python
def test_configures_pulse_range_and_actuation_on_both_channels():
    kit = FakeKit()
    ServoDriver(kit=kit)
    for channel in (0, 1):
        assert kit.servo[channel].actuation_range == SERVO_ACTUATION_RANGE_DEG
        assert kit.servo[channel].pulse_range == (SERVO_MIN_US, SERVO_MAX_US)


def test_apply_delta_accumulates_onto_pose_and_writes_both_channels():
    kit = FakeKit()
    driver = ServoDriver(kit=kit)
    driver.apply_delta(5.0, -5.0)
    assert driver.current == ServoAngles(95.0, 85.0)
    assert kit.servo[0].angle == 95.0
    assert kit.servo[1].angle == 85.0


def test_successive_deltas_accumulate_relative_not_absolute():
    driver = ServoDriver(kit=FakeKit())
    driver.apply_delta(5.0, 0.0)
    driver.apply_delta(5.0, 0.0)
    assert driver.current == ServoAngles(100.0, 90.0)


def test_delta_past_a_limit_is_clamped_and_never_writes_out_of_range():
    kit = FakeKit()
    driver = ServoDriver(kit=kit)
    driver.apply_delta(200.0, 0.0)  # 90 + 200 = 290 -> clamped to 180
    assert driver.current == ServoAngles(180.0, 90.0)
    assert kit.servo[0].angle == 180.0  # the raw 290 is never written


def test_axis_signs_reverse_the_written_direction(monkeypatch):
    monkeypatch.setattr("turret_pi.servo.PAN_SIGN", -1.0)
    driver = ServoDriver(kit=FakeKit())
    driver.apply_delta(5.0, 0.0)  # with PAN_SIGN=-1: 90 + (-1)*5 = 85
    assert driver.current.pan_deg == 85.0


def test_recenter_returns_to_center_after_a_move():
    kit = FakeKit()
    driver = ServoDriver(kit=kit)
    driver.apply_delta(5.0, -5.0)
    driver.recenter()
    assert driver.current == CENTER
    assert kit.servo[0].angle == 90.0
    assert kit.servo[1].angle == 90.0
```

- [ ] **Step 6: Run the full servo suite**

Run: `cd turret && uv run pytest tests/test_servo.py -v`
Expected: PASS — the 5 existing clamp tests plus 7 new `ServoDriver` tests.

- [ ] **Step 7: Add the Pi-only `hardware` extra to pyproject**

In `turret/pyproject.toml`, immediately after the `dependencies = []` line (line 7), add a new section:

```toml
[project.optional-dependencies]
# Pi-only actuator stack: PCA9685 over I²C, speaking degrees. Pulls in adafruit-blinka,
# which only runs on the Pi — so install it there with: uv sync --extra hardware. The
# ServoDriver import is lazy, so Mac tests pass without this extra present.
hardware = [
    "adafruit-circuitpython-servokit",
]
```

- [ ] **Step 8: Verify Mac tests still pass without the extra installed**

Run: `cd turret && uv run pytest -v`
Expected: PASS — proving `turret_pi.servo` imports on the Mac with no `adafruit-blinka` (the lazy import is only reached when `kit=None`, which the tests never do).

- [ ] **Step 9: Commit**

```bash
git add turret/turret_pi/servo.py turret/tests/test_servo.py turret/pyproject.toml
git commit -m "feat(turret): add ServoDriver (I²C actuator) behind an injectable kit seam"
```

---

### Task 2: Teleop calibration harness

> Build-sequence deliverable (spec step 1 / D3): the tool that measures `PAN_SIGN`, `TILT_SIGN`, and the pulse range on real hardware before the tracking loop is closed. The pure key→delta mapping is unit-tested on the Mac; the interactive TTY loop is verified live on the Pi.

**Files:**
- Create: `turret/turret_pi/teleop.py`
- Test: `turret/tests/test_teleop.py`

**Interfaces:**
- Consumes: `ServoDriver` (Task 1) — `apply_delta`, `current`.
- Produces: `STEP_DEG=5.0`, `key_to_delta(key: str, step_deg: float = STEP_DEG) -> tuple[float, float]`, `run_teleop(driver) -> None`, `main() -> int`.

- [ ] **Step 1: Write the failing mapping tests**

Create `turret/tests/test_teleop.py`:

```python
from __future__ import annotations

from turret_pi.teleop import STEP_DEG, key_to_delta


def test_wasd_map_to_signed_nudges():
    assert key_to_delta("d") == (STEP_DEG, 0.0)    # right -> +pan
    assert key_to_delta("a") == (-STEP_DEG, 0.0)   # left  -> -pan
    assert key_to_delta("w") == (0.0, STEP_DEG)    # up    -> +tilt
    assert key_to_delta("s") == (0.0, -STEP_DEG)   # down  -> -tilt


def test_key_is_case_insensitive():
    assert key_to_delta("D") == (STEP_DEG, 0.0)


def test_unknown_key_is_a_no_move():
    assert key_to_delta("x") == (0.0, 0.0)


def test_step_size_is_configurable():
    assert key_to_delta("d", step_deg=2.0) == (2.0, 0.0)
```

- [ ] **Step 2: Run and watch it fail**

Run: `cd turret && uv run pytest tests/test_teleop.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'turret_pi.teleop'`.

- [ ] **Step 3: Implement `teleop.py`**

Create `turret/turret_pi/teleop.py`:

```python
"""Phase-1 teleop harness (ADR-0013): drive the turret from the keyboard to calibrate the
axis-sign constants and pulse range before the tracking loop is closed. Hardware-only — the
pure key->delta mapping is unit-tested on the Mac; the interactive TTY loop is verified live
on the Pi. Run on the Pi with: ``python -m turret_pi.teleop``.
"""

from __future__ import annotations

import sys
import termios
import tty

from .servo import ServoDriver

STEP_DEG = 5.0

# WASD -> unit direction (pan, tilt); scaled by step_deg. Matches the wire contract:
# +pan_delta = target right, +tilt_delta = target up (ADR-0013).
_KEY_DIRECTIONS: dict[str, tuple[float, float]] = {
    "w": (0.0, +1.0),   # tilt up
    "s": (0.0, -1.0),   # tilt down
    "a": (-1.0, 0.0),   # pan left
    "d": (+1.0, 0.0),   # pan right
}


def key_to_delta(key: str, step_deg: float = STEP_DEG) -> tuple[float, float]:
    """Map a WASD keystroke to a ``(pan_delta, tilt_delta)`` nudge in degrees (pure).
    Unknown keys return ``(0.0, 0.0)`` — a no-move."""
    pan_dir, tilt_dir = _KEY_DIRECTIONS.get(key.lower(), (0.0, 0.0))
    return (pan_dir * step_deg, tilt_dir * step_deg)


def run_teleop(driver: ServoDriver) -> None:  # pragma: no cover - interactive/hardware
    """Read single keystrokes from stdin and nudge the driver until ``q``. Prints the pose
    after each move so the operator can read off the sign and range calibration."""
    fd = sys.stdin.fileno()
    original = termios.tcgetattr(fd)
    print("teleop: WASD to nudge, q to quit")
    try:
        tty.setcbreak(fd)
        while True:
            key = sys.stdin.read(1)
            if key == "q":
                break
            pan_delta, tilt_delta = key_to_delta(key)
            if (pan_delta, tilt_delta) != (0.0, 0.0):
                driver.apply_delta(pan_delta, tilt_delta)
                pose = driver.current
                print(f"  pan={pose.pan_deg:.1f}  tilt={pose.tilt_deg:.1f}")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original)


def main() -> int:  # pragma: no cover - hardware entrypoint
    run_teleop(ServoDriver())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
```

- [ ] **Step 4: Run the mapping tests — they pass**

Run: `cd turret && uv run pytest tests/test_teleop.py -v`
Expected: PASS — 4 tests.

- [ ] **Step 5: Commit**

```bash
git add turret/turret_pi/teleop.py turret/tests/test_teleop.py
git commit -m "feat(turret): add Phase-1 keyboard teleop harness for sign/range calibration"
```

---

### Task 3: MJPEG frame streamer

**Files:**
- Create: `turret/turret_pi/streamer.py`
- Modify: `turret/pyproject.toml` (add `opencv-python` to base `dependencies`)
- Test: `turret/tests/test_streamer.py`

**Interfaces:**
- Consumes: nothing from earlier tasks; uses `cv2` and stdlib `http.server`.
- Produces: `run_streamer(camera_index: int = 0, port: int = 8000, *, path: str = "/stream.mjpg", should_continue: Callable[[], bool] = lambda: True) -> None`, plus helpers `_encode_part(jpeg: bytes) -> bytes` and `_open_camera(camera_index: int) -> cv2.VideoCapture`.

- [ ] **Step 1: Add `opencv-python` to base dependencies**

In `turret/pyproject.toml`, change line 7 from:

```toml
dependencies = []
```

to:

```toml
dependencies = [
    "opencv-python",  # camera capture + MJPEG encode (streamer); cross-platform, so Mac tests can import it
]
```

- [ ] **Step 2: Sync so `cv2` is importable in the turret venv**

Run: `cd turret && uv sync`
Expected: resolves and installs `opencv-python` (and numpy) into `turret/.venv`.

- [ ] **Step 3: Write the failing byte-framing test**

Create `turret/tests/test_streamer.py`:

```python
from __future__ import annotations

from unittest import mock

import pytest

from turret_pi.streamer import _encode_part, _open_camera


def test_encode_part_frames_jpeg_as_a_multipart_chunk():
    part = _encode_part(b"JPEGDATA")
    assert part == (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n"
        b"Content-Length: 8\r\n\r\n"
        b"JPEGDATA\r\n"
    )
```

- [ ] **Step 4: Run and watch it fail**

Run: `cd turret && uv run pytest tests/test_streamer.py::test_encode_part_frames_jpeg_as_a_multipart_chunk -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'turret_pi.streamer'`.

- [ ] **Step 5: Implement `streamer.py`**

Create `turret/turret_pi/streamer.py`:

```python
"""Frame streamer (ADR-0013 Phase 2): capture the Pi's USB camera and serve it as MJPEG over
HTTP so the Mac's existing ``CameraSource`` opens it as a plain stream URL — zero new Mac code.
Stdlib ``http.server`` + OpenCV only (KISS): the client is a ``cv2.VideoCapture``, not a
browser, so a minimal ``multipart/x-mixed-replace`` server suffices.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

import cv2

_BOUNDARY = "frame"
_BIND_HOST = "0.0.0.0"  # serve on all interfaces so the Mac on the LAN can reach it
_POLL_TIMEOUT_S = 0.5   # how often the accept loop re-checks should_continue while idle


def _encode_part(jpeg: bytes) -> bytes:
    """Frame one JPEG as a ``multipart/x-mixed-replace`` part (pure; unit-tested on the Mac)."""
    return (
        b"--" + _BOUNDARY.encode() + b"\r\n"
        b"Content-Type: image/jpeg\r\n"
        b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
        + jpeg + b"\r\n"
    )


def _open_camera(camera_index: int) -> cv2.VideoCapture:
    """Open the capture device or raise a clear error (mirrors ``CameraSource``)."""
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"could not open camera source: {camera_index!r}")
    return cap


def run_streamer(
    camera_index: int = 0,
    port: int = 8000,
    *,
    path: str = "/stream.mjpg",
    should_continue: Callable[[], bool] = lambda: True,
) -> None:
    """Blocking: capture ``camera_index``, MJPEG-encode each frame, and serve
    ``multipart/x-mixed-replace; boundary=frame`` at ``http://<pi>:<port><path>``. Runs until
    ``should_continue()`` is False (main runs it on a daemon thread)."""
    cap = _open_camera(camera_index)

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != path:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header(
                "Content-Type", f"multipart/x-mixed-replace; boundary={_BOUNDARY}"
            )
            self.end_headers()
            while should_continue():
                ok, frame = cap.read()
                if not ok:
                    break
                encoded, jpeg = cv2.imencode(".jpg", frame)
                if not encoded:
                    continue
                try:
                    self.wfile.write(_encode_part(jpeg.tobytes()))
                except (BrokenPipeError, ConnectionResetError):
                    break  # the client (the Mac) went away — end this response cleanly

        def log_message(self, *args) -> None:
            return  # quiet; the listener owns the console

    server = ThreadingHTTPServer((_BIND_HOST, port), _Handler)
    server.daemon_threads = True   # don't let a lingering stream thread block process exit
    server.timeout = _POLL_TIMEOUT_S
    try:
        while should_continue():
            server.handle_request()
    finally:
        server.server_close()
        cap.release()
```

- [ ] **Step 6: Run the byte-framing test — it passes**

Run: `cd turret && uv run pytest tests/test_streamer.py::test_encode_part_frames_jpeg_as_a_multipart_chunk -v`
Expected: PASS.

- [ ] **Step 7: Add the open-failure test**

Append to `turret/tests/test_streamer.py`:

```python
def test_open_camera_raises_a_clear_error_when_the_device_wont_open():
    fake_cap = mock.Mock()
    fake_cap.isOpened.return_value = False
    with mock.patch("turret_pi.streamer.cv2.VideoCapture", return_value=fake_cap):
        with pytest.raises(RuntimeError, match="could not open camera source: 7"):
            _open_camera(7)
```

- [ ] **Step 8: Run the streamer suite**

Run: `cd turret && uv run pytest tests/test_streamer.py -v`
Expected: PASS — both tests.

- [ ] **Step 9: Commit**

```bash
git add turret/turret_pi/streamer.py turret/tests/test_streamer.py turret/pyproject.toml
git commit -m "feat(turret): add MJPEG frame streamer over stdlib http.server"
```

> **Live verification (Phase 2, on the rig — not a unit test):** on the Pi, run the streamer, open `http://<pi-ip>:8000/stream.mjpg` in VLC/a browser to confirm live video, then on the Mac run `uv run track --source http://<pi-ip>:8000/stream.mjpg --track` and confirm `#id` boxes on the turret feed. Measure end-to-end latency here (the number ADR-0013's control design hinges on).

---

### Task 4: `main` entrypoint + process lifecycle

**Files:**
- Create: `turret/turret_pi/main.py`
- Test: `turret/tests/test_main.py`

**Interfaces:**
- Consumes: `ServoDriver` (Task 1) — `.recenter()`; `run_streamer` (Task 3); `run_listener(servo, port, *, host, allowed_source, should_continue)` (already built).
- Produces: `main(argv: list[str] | None = None) -> int`, `run_turret(driver, args, stop, *, start_streamer=..., listener=run_listener) -> int`, `_parse_args(argv) -> argparse.Namespace`.

- [ ] **Step 1: Write the failing arg-parsing test**

Create `turret/tests/test_main.py`:

```python
from __future__ import annotations

import threading

from turret_pi.main import _parse_args, run_turret


def test_parse_args_defaults():
    args = _parse_args([])
    assert args.port == 9000
    assert args.stream_port == 8000
    assert args.camera_index == 0
    assert args.host == "0.0.0.0"
    assert args.allowed_source is None


def test_parse_args_overrides():
    args = _parse_args(
        ["--port", "9100", "--stream-port", "8100", "--camera-index", "2",
         "--host", "127.0.0.1", "--allowed-source", "10.0.0.5"]
    )
    assert (args.port, args.stream_port, args.camera_index) == (9100, 8100, 2)
    assert args.host == "127.0.0.1"
    assert args.allowed_source == "10.0.0.5"
```

- [ ] **Step 2: Run and watch it fail**

Run: `cd turret && uv run pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'turret_pi.main'`.

- [ ] **Step 3: Implement `main.py`**

Create `turret/turret_pi/main.py`:

```python
"""turret entrypoint (ADR-0013): wire the ServoDriver, the MJPEG streamer, and the UDP
command listener into one process. The listener owns the **main thread** (safety-critical —
it moves motors, so SIGINT/SIGTERM interrupt it directly); the streamer runs on a **daemon
thread**. Deploy under systemd (``Restart=on-failure``). On exit the servos are recentered
to a known safe pose.
"""

from __future__ import annotations

import argparse
import signal
import threading
from typing import Callable

from .listener import run_listener
from .servo import ServoDriver
from .streamer import run_streamer

DEFAULT_PORT = 9000
DEFAULT_STREAM_PORT = 8000
DEFAULT_CAMERA_INDEX = 0
DEFAULT_HOST = "0.0.0.0"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="turret", description="Pan-tilt tracking turret (Raspberry Pi side)."
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="UDP Aim Command port")
    parser.add_argument("--stream-port", type=int, default=DEFAULT_STREAM_PORT,
                        help="HTTP MJPEG port")
    parser.add_argument("--camera-index", type=int, default=DEFAULT_CAMERA_INDEX,
                        help="OpenCV camera index")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="listener bind host")
    parser.add_argument("--allowed-source", default=None,
                        help="only accept datagrams from this source IP (defense-in-depth)")
    return parser.parse_args(argv)


def _start_streamer_thread(
    args: argparse.Namespace, should_continue: Callable[[], bool]
) -> threading.Thread:
    thread = threading.Thread(
        target=run_streamer,
        kwargs={
            "camera_index": args.camera_index,
            "port": args.stream_port,
            "should_continue": should_continue,
        },
        daemon=True,
    )
    thread.start()
    return thread


def run_turret(
    driver: ServoDriver,
    args: argparse.Namespace,
    stop: threading.Event,
    *,
    start_streamer: Callable[..., threading.Thread] = _start_streamer_thread,
    listener: Callable[..., None] = run_listener,
) -> int:
    """Start the streamer thread, then run the listener on this thread until ``stop`` is set;
    recenter the servos on the way out. ``start_streamer``/``listener`` are injectable seams
    so the wiring is testable with fakes and no hardware."""
    should_continue = lambda: not stop.is_set()
    start_streamer(args, should_continue)  # driver already built -> a servo fault failed fast
    try:
        listener(
            driver,
            args.port,
            host=args.host,
            allowed_source=args.allowed_source,
            should_continue=should_continue,
        )
    except KeyboardInterrupt:
        stop.set()
    finally:
        stop.set()          # tell the streamer thread to wind down too
        driver.recenter()   # leave the turret in a known safe pose
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    driver = ServoDriver()  # build first: a HAT fault fails before we advertise a stream
    return run_turret(driver, args, stop)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
```

- [ ] **Step 4: Run the arg tests — they pass**

Run: `cd turret && uv run pytest tests/test_main.py -v`
Expected: PASS — both `_parse_args` tests.

- [ ] **Step 5: Add the wiring test (order + recenter, no hardware)**

Append to `turret/tests/test_main.py`:

```python
class _FakeDriver:
    """A ServoDriver stand-in: records recenter() calls; no HAT."""

    def __init__(self) -> None:
        self.recentered = 0

    def recenter(self) -> None:
        self.recentered += 1


def test_run_turret_starts_streamer_before_listener_then_recenters_on_exit():
    driver = _FakeDriver()
    calls: list = []

    def fake_start_streamer(args, should_continue):
        calls.append("streamer")
        return threading.Thread(target=lambda: None)  # never started; wiring test only

    def fake_listener(servo, port, *, host, allowed_source, should_continue):
        calls.append(("listener", servo, port, host, allowed_source))
        # returns immediately, as if should_continue() had already gone False

    args = _parse_args(["--port", "9000", "--host", "127.0.0.1"])
    stop = threading.Event()

    rc = run_turret(
        driver, args, stop,
        start_streamer=fake_start_streamer,
        listener=fake_listener,
    )

    assert rc == 0
    assert calls[0] == "streamer"                       # streamer first (startup order)
    assert calls[1][0] == "listener"                    # then the listener
    assert calls[1][1] is driver and calls[1][2] == 9000  # driver + port wired through
    assert calls[1][3] == "127.0.0.1"                   # host forwarded
    assert driver.recentered == 1                       # recentered on the way out
    assert stop.is_set()                                # streamer told to wind down
```

- [ ] **Step 6: Run the full main suite**

Run: `cd turret && uv run pytest tests/test_main.py -v`
Expected: PASS — 3 tests.

- [ ] **Step 7: Confirm the `turret` entrypoint resolves**

Run: `cd turret && uv run python -c "from turret_pi.main import main; print('entrypoint ok')"`
Expected: prints `entrypoint ok` (the `turret = "turret_pi.main:main"` script in `pyproject.toml` is no longer dangling).

- [ ] **Step 8: Run the whole turret suite green**

Run: `cd turret && uv run pytest -v`
Expected: PASS — every test across servo, teleop, streamer, main, listener, wire.

- [ ] **Step 9: Commit**

```bash
git add turret/turret_pi/main.py turret/tests/test_main.py
git commit -m "feat(turret): add main entrypoint wiring driver, streamer, and listener"
```

---

## Post-implementation (hardware, on the Pi — not part of the coded tasks)

These are the spec's build-sequence checkpoints that require the rig. Do them in order after Task 4; none is a unit test.

1. **Calibrate (Task 1 + 2):** `uv sync --extra hardware` on the Pi, then `python -m turret_pi.teleop`. Drive with WASD to find `PAN_SIGN`/`TILT_SIGN` (the classic first bug — ADR-0013 Risks) and a pulse range where the servos don't buzz/strain at the ends. Freeze the measured values into the constants in `servo.py`. *Done when a keyboard aims the turret correctly.*
2. **Stream (Task 3):** live-verify per the Task 3 verification note; measure end-to-end latency.
3. **Close the loop (Task 4):** run `turret --port 9000 --stream-port 8000` on the Pi under systemd (`ExecStart=… turret …`, `Restart=on-failure`), then on the Mac `uv run track --source http://<pi-ip>:8000/stream.mjpg --track --turret <pi-ip>:9000`. *Done when the turret follows a target (Phase 3, jittery P — expected).*
4. **Tune (Phase 4):** `--turret-kp/-ki/-kd` once the P loop is seen to overshoot.

## Deferred (tracked, not in this plan)

- **HMAC-signed datagrams** — the control plane is unauthenticated UDP (spoofable source IPs). Per ADR-0013's trust model this is the prerequisite before the turret drives anything dangerous. Noted here so it is not forgotten.

## Self-Review

- **Spec coverage:** ServoDriver (§Component 1) → Task 1; teleop/calibration (§D3, build step 1) → Task 2; run_streamer + `_encode_part` helper (§Component 2) → Task 3; main/wiring/shutdown/recenter (§Component 3) → Task 4; dependencies (§"Dependencies to add") → Task 1 (extra) + Task 3 (base); testing strategy table (§Testing strategy) → the fake-kit / pure-helper / fake-driver tests in each task. D1 (ServoKit), D2 (pin channels), D4 (ports/args), D5 (threading model) are all realized. Deferred HMAC and hardware checkpoints are captured above.
- **Deviations flagged:** recenter-via-`recenter()` (not `apply_delta`); Pi-only deps in an optional extra (not base); teleop included beyond the 3-file scope table. All three are documented under "Planner decisions" with rationale for the reviewer.
- **Type consistency:** `ServoAngles`, `clamp_angles`, `CENTER`, `PAN_SIGN`/`TILT_SIGN`, `ServoDriver.recenter`, `run_streamer(camera_index, port, *, path, should_continue)`, `run_listener(servo, port, *, host, allowed_source, should_continue)`, and `run_turret(driver, args, stop, *, start_streamer, listener)` are used with identical signatures everywhere they appear.
