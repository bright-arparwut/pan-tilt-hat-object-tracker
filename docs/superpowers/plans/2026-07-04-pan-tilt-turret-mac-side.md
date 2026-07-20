# Pan-Tilt Turret — Mac-Side Actuator Sink Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the turret as a new `FrameSink` — an Actuator Sink that turns each frame's
tracked boxes into a UDP Aim Command — plus every piece of that path that is testable
**without physical hardware**: config, the pure Target Selector and Aim Controller, the wire
encode/decode, the CLI flags, and the widened `FrameSink`/`pipeline.run` seam.

**Architecture:** The turret enters the pipeline as one more `FrameSink` (ADR-0010/0013),
composing with the existing `WindowSink`/`VideoFileSink` via `CompositeSink` exactly like
`--record` does today. Two new pure units — `select_target` (lock-first-id) and
`aim_controller.step` (P/PID) — are threaded by a thin stateful `ActuatorSink`, mirroring the
pure-step-wrapped-in-a-stateful-manager shape `zoom.py`'s `ZoomSlots` already uses. The one
change to existing, tested code is widening `FrameSink.show` with an optional `tracks`
parameter so `pipeline.run` can hand the Actuator Sink the frame's confirmed Tracks.

**Tech Stack:** Python 3.10+, `supervision` (`sv.Detections`), stdlib `socket`/`json` only —
no new dependency on the Mac side. Pi-side pure units live in a separate `turret/` package
(`turret_pi`), installable independently, with its own `pyproject.toml` and its own `pytest`
run.

## Global Constraints

- Python `>=3.10` (matches the repo root `pyproject.toml`'s `requires-python`).
- **No new Mac-side dependency.** The Actuator Sink's network I/O is stdlib `socket` + `json`
  only (spec's Design decisions: "No new deps — Mac side uses only stdlib").
- **`turret/` is a separate installable package** (`turret-pi`, importable as `turret_pi`),
  not merged into `object_tracker` — different runtime host, disjoint dependency graph,
  different deploy lifecycle (spec's Design decisions).
- **No shared code module between Mac and Pi.** Each side independently encodes/decodes the
  same documented wire shape (`{"pan_delta": float, "tilt_delta": float, "seq": int}`); do
  not import across the `object_tracker` / `turret_pi` boundary.
- **`FrameSink.show` widens with a backward-compatible optional parameter** —
  `show(self, frame, tracks=None)`. Every existing single-arg call site (`sink.show(frame)`)
  must keep working unchanged.
- **`pipeline.run()`'s own parameter list does not change.** The only diff inside `run` is
  threading the already-computed `confirmed` Detections into the existing `sink.show(...)`
  call as a second argument.
- **Target selection is lock-first-id (ADR-0013), not configurable in v1.** Latch the first
  stable `#id` seen; hold position (send nothing) while unlocked; re-latch on the next
  present id once the old one is gone.
- **Command channel is fire-and-forget UDP — no ack/retry.** A dropped Aim Command is
  superseded by the next one; do not add retry logic.
- **Scope boundary (locked with the user):** this plan covers only what's testable without
  a physical Pi/HAT: `object_tracker/turret_sink/*`, the `sinks.py`/`pipeline.py`/`cli.py`
  integration, and the **pure** half of the Pi package (`turret_pi.servo.clamp_angles`,
  `turret_pi.wire.decode`). The real I²C `ServoDriver`, `streamer.py`, `listener.py`, and
  `turret_pi/main.py` are explicitly **out of scope** — a follow-up plan once Phase 0
  hardware bring-up has picked a concrete HAT SDK (spec's own "Open item for Phase 1").

---

### Task 1: Turret config — `AimGains` + `TurretConfig`

**Files:**
- Modify: `object_tracker/config.py`

**Interfaces:**
- Produces: `AimGains(kp, ki=0.0, kd=0.0, deadzone_px=6.0, max_delta_deg=5.0)` (frozen
  dataclass), `TurretConfig(host, port, gains)` (frozen dataclass), and the constants
  `DEFAULT_TURRET_KP/KI/KD/DEADZONE_PX/MAX_DELTA_DEG/PORT` — every later task in this plan
  imports these from `object_tracker.config`.

No dedicated test file for this task: `TrackConfig`/`ZoomConfig` (the two existing sibling
config dataclasses) have no tests of their own either — they're plain data holders exercised
indirectly wherever they're constructed (see `tests/test_detection.py`, `tests/test_io.py`).
`AimGains`/`TurretConfig` are exercised the same way starting in Task 2.

- [ ] **Step 1: Add the defaults/constants block**

Insert after the existing `DEFAULT_ZOOM_SIZE = 0.05` line (`object_tracker/config.py:64`):

```python
# --- turret (ADR-0013) — Aim Controller defaults; deliberately gentle, tune on hardware ---
DEFAULT_TURRET_KP = 0.05  # deg per px error
DEFAULT_TURRET_KI = 0.0  # Phase 3 is P-only; Phase 4 turns this on
DEFAULT_TURRET_KD = 0.0  # ditto
DEFAULT_TURRET_DEADZONE_PX = 6.0  # |error| below this is treated as zero (kills at-rest jitter)
DEFAULT_TURRET_MAX_DELTA_DEG = 5.0  # per-step slew clamp on a single Aim Command
DEFAULT_TURRET_PORT = 9000
```

- [ ] **Step 2: Add the two frozen dataclasses**

Append at the end of `object_tracker/config.py` (after the `ZoomConfig` class):

```python
@dataclass(frozen=True)
class AimGains:
    """Aim Controller gains (ADR-0013): P-only when ``ki == kd == 0.0`` (Phase 3); the same
    ``aim_controller.step`` becomes PID (Phase 4) purely by which gains are nonzero."""

    kp: float
    ki: float = DEFAULT_TURRET_KI
    kd: float = DEFAULT_TURRET_KD
    deadzone_px: float = DEFAULT_TURRET_DEADZONE_PX
    max_delta_deg: float = DEFAULT_TURRET_MAX_DELTA_DEG


@dataclass(frozen=True)
class TurretConfig:
    """Turret Actuator Sink settings for a run (ADR-0013): where Aim Commands are sent."""

    host: str
    port: int
    gains: AimGains
```

- [ ] **Step 3: Run the full suite to confirm nothing broke**

Run: `uv run pytest -q`
Expected: PASS (same count as before this change — this step only adds unused-so-far code)

- [ ] **Step 4: Commit**

```bash
git add object_tracker/config.py
git commit -m "feat: add AimGains/TurretConfig for the turret Actuator Sink (ADR-0013)"
```

---

### Task 2: Target Selector — pure lock-first-id policy

**Files:**
- Create: `object_tracker/turret_sink/__init__.py`
- Create: `object_tracker/turret_sink/target_selector.py`
- Test: `tests/test_target_selector.py`

**Interfaces:**
- Consumes: nothing (no dependency on Task 1).
- Produces: `select_target(present_ids: frozenset[int], prior_lock: int | None) -> int | None`
  — consumed by `ActuatorSink` in Task 10.

- [ ] **Step 1: Create the package marker**

```python
# object_tracker/turret_sink/__init__.py
"""turret_sink — the Mac-side Actuator Sink for the pan-tilt tracking turret (ADR-0013).

Filled in incrementally across this plan; re-exports land once every module in the package
exists (see the final `__init__.py` task).
"""

from __future__ import annotations
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_target_selector.py
"""Unit tests for the Target Selector (ADR-0013): pure lock-first-id policy.

No hardware, no YOLO — table-driven over synthetic present-id sets.
"""

from __future__ import annotations

import pytest

from object_tracker.turret_sink.target_selector import select_target


@pytest.mark.parametrize(
    "present_ids, prior_lock, expected",
    [
        (frozenset(), None, None),  # nothing present, never locked -> unlocked
        (frozenset(), 5, None),  # locked id vanished entirely -> unlocked (v1 holds position)
        (frozenset({3, 7}), None, 3),  # first lock: smallest present id (first-seen)
        (frozenset({3, 7}), 3, 3),  # keep the lock while it's present
        (frozenset({3, 7}), 7, 7),  # keep the *existing* lock even though 3 is also present
        (frozenset({3, 7}), 5, 3),  # old lock (5) gone -> re-latch smallest present
        (frozenset({9}), 3, 9),  # old lock (3) gone, only 9 present -> lock 9
    ],
)
def test_select_target(present_ids, prior_lock, expected):
    assert select_target(present_ids, prior_lock) == expected
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_target_selector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'object_tracker.turret_sink.target_selector'`

- [ ] **Step 4: Write the implementation**

```python
# object_tracker/turret_sink/target_selector.py
"""Target Selector (ADR-0013): pure lock-first-id policy — pick which Track the Actuator
Sink follows.
"""

from __future__ import annotations


def select_target(present_ids: frozenset[int], prior_lock: int | None) -> int | None:
    """Lock-first-id (ADR-0013): keep ``prior_lock`` while it's present; otherwise lock the
    smallest present id (ByteTrack ids are monotonic, so the smallest present id is the
    first-seen one — the same trick ``zoom.py``'s ``ZoomSlots`` uses). No ids present at all
    -> unlocked (``None``); the caller (``ActuatorSink``) holds position in that case rather
    than snapping anywhere (v1, ADR-0013)."""
    if not present_ids:
        return None
    if prior_lock is not None and prior_lock in present_ids:
        return prior_lock
    return min(present_ids)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_target_selector.py -v`
Expected: PASS (7 passed)

- [ ] **Step 6: Commit**

```bash
git add object_tracker/turret_sink/__init__.py object_tracker/turret_sink/target_selector.py tests/test_target_selector.py
git commit -m "feat: add Target Selector (lock-first-id policy, ADR-0013)"
```

---

### Task 3: Aim Controller — pure P/PID step

**Files:**
- Create: `object_tracker/turret_sink/aim_controller.py`
- Test: `tests/test_aim_controller.py`

**Interfaces:**
- Consumes: `AimGains` from `object_tracker.config` (Task 1).
- Produces: `AimCommand(pan_delta, tilt_delta)`, `AimControllerState(integral_x=0.0,
  integral_y=0.0, prev_error_x=0.0, prev_error_y=0.0)` (both frozen dataclasses), and
  `step(error_px: tuple[float, float], gains: AimGains, prev_state: AimControllerState, dt:
  float) -> tuple[AimCommand, AimControllerState]` — consumed by `ActuatorSink` in Task 10.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_aim_controller.py
"""Unit tests for the Aim Controller (ADR-0013): pure P/PID step.

No hardware, no network — exercises ``step`` directly with synthetic pixel errors.
"""

from __future__ import annotations

import pytest

from object_tracker.config import AimGains
from object_tracker.turret_sink.aim_controller import AimControllerState, step

FRAME_ZERO = AimControllerState()


def _p_gains(**overrides):
    base = dict(kp=0.1, ki=0.0, kd=0.0, deadzone_px=5.0, max_delta_deg=10.0)
    base.update(overrides)
    return AimGains(**base)


def test_error_inside_deadzone_produces_zero_command():
    command, new_state = step((3.0, -2.0), _p_gains(), FRAME_ZERO, dt=0.1)
    assert command.pan_delta == pytest.approx(0.0)
    assert command.tilt_delta == pytest.approx(0.0)
    assert new_state == AimControllerState(0.0, 0.0, 0.0, 0.0)


def test_pan_follows_positive_x_error_directly():
    command, _ = step((20.0, 0.0), _p_gains(), FRAME_ZERO, dt=0.1)
    assert command.pan_delta == pytest.approx(2.0)  # kp * error = 0.1 * 20


def test_tilt_inverts_the_sign_of_y_error():
    # +y (target below centre, image coords) must drive tilt_delta *negative* (+up convention).
    command, _ = step((0.0, 20.0), _p_gains(), FRAME_ZERO, dt=0.1)
    assert command.tilt_delta == pytest.approx(-2.0)


def test_output_clamps_at_positive_max_delta():
    command, _ = step((1000.0, 0.0), _p_gains(), FRAME_ZERO, dt=0.1)
    assert command.pan_delta == pytest.approx(10.0)


def test_output_clamps_at_negative_max_delta():
    command, _ = step((-1000.0, 0.0), _p_gains(), FRAME_ZERO, dt=0.1)
    assert command.pan_delta == pytest.approx(-10.0)


def test_integral_term_accumulates_across_steps():
    gains = _p_gains(kp=0.0, ki=1.0, deadzone_px=0.0, max_delta_deg=100.0)
    command1, state1 = step((10.0, 0.0), gains, AimControllerState(), dt=1.0)
    assert command1.pan_delta == pytest.approx(10.0)  # ki * (0 + 10*1)
    command2, state2 = step((10.0, 0.0), gains, state1, dt=1.0)
    assert state2.integral_x == pytest.approx(20.0)
    assert command2.pan_delta == pytest.approx(20.0)  # ki * (10 + 10*1)


def test_derivative_term_reacts_only_to_the_change_in_error():
    gains = _p_gains(kp=0.0, ki=0.0, kd=1.0, deadzone_px=0.0, max_delta_deg=100.0)
    command1, state1 = step((10.0, 0.0), gains, AimControllerState(), dt=1.0)
    assert command1.pan_delta == pytest.approx(10.0)  # kd * (10 - 0) / 1
    command2, _ = step((10.0, 0.0), gains, state1, dt=1.0)
    assert command2.pan_delta == pytest.approx(0.0)  # kd * (10 - 10) / 1


def test_zero_dt_does_not_raise_and_yields_no_derivative_contribution():
    gains = _p_gains(kp=0.0, ki=0.0, kd=1.0, deadzone_px=0.0, max_delta_deg=100.0)
    command, _ = step((10.0, 0.0), gains, AimControllerState(), dt=0.0)
    assert command.pan_delta == pytest.approx(0.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_aim_controller.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'object_tracker.turret_sink.aim_controller'`

- [ ] **Step 3: Write the implementation**

```python
# object_tracker/turret_sink/aim_controller.py
"""Aim Controller (ADR-0013): pure P/PID step from pixel error to an Aim Command."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import AimGains


@dataclass(frozen=True)
class AimCommand:
    """A relative servo nudge (ADR-0013): ``pan_delta`` +right, ``tilt_delta`` +up."""

    pan_delta: float
    tilt_delta: float


@dataclass(frozen=True)
class AimControllerState:
    """Threaded PID state — one integral/previous-error pair per axis."""

    integral_x: float = 0.0
    integral_y: float = 0.0
    prev_error_x: float = 0.0
    prev_error_y: float = 0.0


def _pid_axis(
    error: float, gains: AimGains, integral: float, prev_error: float, dt: float
) -> tuple[float, float, float]:
    """One axis of PID. Returns ``(clamped_output, new_integral, deadzone_applied_error)``."""
    error = 0.0 if abs(error) < gains.deadzone_px else error
    new_integral = integral + error * dt
    derivative = (error - prev_error) / dt if dt > 0 else 0.0
    output = gains.kp * error + gains.ki * new_integral + gains.kd * derivative
    clamped = max(-gains.max_delta_deg, min(gains.max_delta_deg, output))
    return clamped, new_integral, error


def step(
    error_px: tuple[float, float],
    gains: AimGains,
    prev_state: AimControllerState,
    dt: float,
) -> tuple[AimCommand, AimControllerState]:
    """Pure P (``ki == kd == 0``, Phase 3) / PID (Phase 4) step — same function, only the
    gains change between phases (ADR-0013).

    ``error_px`` is ``target_center - frame_center`` in image pixels: +x right, +y down.
    Pan follows +x directly. Tilt inverts the sign: image +y (target below centre) must
    drive the camera to look further down, which is ``AimCommand``'s *negative* tilt_delta
    (tilt_delta is +up) — the sign flip the spec's Risks section calls out as the classic
    first bug.
    """
    error_x, error_y = error_px
    pan, integral_x, prev_error_x = _pid_axis(
        error_x, gains, prev_state.integral_x, prev_state.prev_error_x, dt
    )
    tilt_raw, integral_y, prev_error_y = _pid_axis(
        error_y, gains, prev_state.integral_y, prev_state.prev_error_y, dt
    )
    command = AimCommand(pan_delta=pan, tilt_delta=-tilt_raw)
    new_state = AimControllerState(
        integral_x=integral_x,
        integral_y=integral_y,
        prev_error_x=prev_error_x,
        prev_error_y=prev_error_y,
    )
    return command, new_state
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_aim_controller.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add object_tracker/turret_sink/aim_controller.py tests/test_aim_controller.py
git commit -m "feat: add Aim Controller pure P/PID step (ADR-0013)"
```

---

### Task 4: Wire protocol — Mac-side encode

**Files:**
- Create: `object_tracker/turret_sink/wire.py`
- Test: `tests/test_turret_wire.py`

**Interfaces:**
- Consumes: `AimCommand` from `object_tracker.turret_sink.aim_controller` (Task 3).
- Produces: `encode(command: AimCommand, seq: int) -> bytes` — consumed by
  `UdpAimTransport` in Task 5.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_turret_wire.py
"""Unit tests for the Mac-side wire encode (ADR-0013): one JSON object per UDP datagram."""

from __future__ import annotations

import json

from object_tracker.turret_sink.aim_controller import AimCommand
from object_tracker.turret_sink.wire import encode


def test_encode_round_trips_through_json():
    payload = json.loads(encode(AimCommand(pan_delta=-2.3, tilt_delta=0.8), seq=1042))
    assert payload == {"pan_delta": -2.3, "tilt_delta": 0.8, "seq": 1042}


def test_encode_returns_bytes():
    assert isinstance(encode(AimCommand(0.0, 0.0), seq=1), bytes)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_turret_wire.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'object_tracker.turret_sink.wire'`

- [ ] **Step 3: Write the implementation**

```python
# object_tracker/turret_sink/wire.py
"""Wire protocol — Mac-side half (ADR-0013). One JSON object per UDP datagram:
``{"pan_delta": ..., "tilt_delta": ..., "seq": ...}``. No shared module with the Pi side
(ADR-0013: separate deployables/deps) — ``turret_pi.wire`` independently decodes the same
documented shape.
"""

from __future__ import annotations

import json

from .aim_controller import AimCommand


def encode(command: AimCommand, seq: int) -> bytes:
    """Encode one Aim Command as a UDP datagram payload."""
    payload = {"pan_delta": command.pan_delta, "tilt_delta": command.tilt_delta, "seq": seq}
    return json.dumps(payload).encode("utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_turret_wire.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add object_tracker/turret_sink/wire.py tests/test_turret_wire.py
git commit -m "feat: add turret_sink wire encode (ADR-0013)"
```

---

### Task 5: Aim Transport — fire-and-forget UDP

**Files:**
- Create: `object_tracker/turret_sink/transport.py`
- Test: `tests/test_transport.py`

**Interfaces:**
- Consumes: `AimCommand` (Task 3), `encode` (Task 4).
- Produces: `AimTransport` Protocol (`send(command) -> None`, `close() -> None`) and
  `UdpAimTransport(host: str, port: int)` implementing it — consumed by `ActuatorSink`
  (Task 10) and `cli.py` (Task 12).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_transport.py
"""Unit tests for UdpAimTransport (ADR-0013) — fire-and-forget UDP, no ack/retry.

The real socket is monkeypatched (mirrors how tests/test_sinks.py monkeypatches cv2) so no
network I/O happens in the test suite.
"""

from __future__ import annotations

import json

from object_tracker.turret_sink import transport
from object_tracker.turret_sink.aim_controller import AimCommand
from object_tracker.turret_sink.transport import UdpAimTransport


class FakeSocket:
    def __init__(self):
        self.sent: list[tuple[bytes, tuple]] = []
        self.closed = False

    def sendto(self, payload, addr):
        self.sent.append((payload, addr))

    def close(self):
        self.closed = True


def _patch_socket(monkeypatch) -> FakeSocket:
    fake = FakeSocket()
    monkeypatch.setattr(transport.socket, "socket", lambda *a, **k: fake)
    return fake


def test_send_increments_seq_each_call(monkeypatch):
    fake = _patch_socket(monkeypatch)
    t = UdpAimTransport("pi.local", 9000)

    t.send(AimCommand(1.0, 2.0))
    t.send(AimCommand(3.0, 4.0))

    seqs = [json.loads(payload)["seq"] for payload, _ in fake.sent]
    assert seqs == [1, 2]


def test_send_targets_the_configured_address(monkeypatch):
    fake = _patch_socket(monkeypatch)
    t = UdpAimTransport("pi.local", 9000)

    t.send(AimCommand(1.0, 2.0))

    _, addr = fake.sent[0]
    assert addr == ("pi.local", 9000)


def test_send_payload_matches_command(monkeypatch):
    fake = _patch_socket(monkeypatch)
    t = UdpAimTransport("pi.local", 9000)

    t.send(AimCommand(pan_delta=-1.5, tilt_delta=0.5))

    payload = json.loads(fake.sent[0][0])
    assert payload["pan_delta"] == -1.5
    assert payload["tilt_delta"] == 0.5


def test_close_closes_the_socket(monkeypatch):
    fake = _patch_socket(monkeypatch)
    UdpAimTransport("pi.local", 9000).close()
    assert fake.closed is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_transport.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'object_tracker.turret_sink.transport'`

- [ ] **Step 3: Write the implementation**

```python
# object_tracker/turret_sink/transport.py
"""Aim Transport (ADR-0013): the sole Mac-side network I/O, fire-and-forget UDP."""

from __future__ import annotations

import socket
from typing import Protocol

from .aim_controller import AimCommand
from .wire import encode


class AimTransport(Protocol):
    def send(self, command: AimCommand) -> None: ...

    def close(self) -> None: ...


class UdpAimTransport:
    """Fire-and-forget UDP (ADR-0013): a dropped Aim Command is superseded by the next one
    ~30-60ms later, so there is no ack/retry — retrying a stale command is worse than
    dropping it."""

    def __init__(self, host: str, port: int) -> None:
        self._addr = (host, port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._seq = 0

    def send(self, command: AimCommand) -> None:
        self._seq += 1
        self._sock.sendto(encode(command, self._seq), self._addr)

    def close(self) -> None:
        self._sock.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_transport.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add object_tracker/turret_sink/transport.py tests/test_transport.py
git commit -m "feat: add UdpAimTransport, fire-and-forget UDP (ADR-0013)"
```

---

### Task 6: Turret package scaffold + pure `ServoAngles`/`clamp_angles`

**Files:**
- Create: `turret/pyproject.toml`
- Create: `turret/README.md`
- Create: `turret/turret_pi/__init__.py`
- Create: `turret/turret_pi/servo.py`
- Test: `turret/tests/test_servo.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ServoAngles(pan_deg, tilt_deg)` (frozen dataclass) and `clamp_angles(angles:
  ServoAngles) -> ServoAngles` — the pure half of the Phase 1 servo driver. The real I²C
  `ServoDriver` is out of scope (Global Constraints) and is a follow-up plan.

This is a **separate installable package** from `object_tracker` (own `pyproject.toml`, own
`pytest` run) — see Global Constraints. Its tests run with their own `uv sync` inside
`turret/`, not from the repo root.

- [ ] **Step 1: Scaffold the package files**

```toml
# turret/pyproject.toml
[project]
name = "turret-pi"
version = "0.1.0"
description = "Pi-side actuator for the pan-tilt tracking turret (ADR-0013): servo driver, frame streamer, command listener. Runs on the Raspberry Pi only."
readme = "README.md"
requires-python = ">=3.10"
dependencies = []

[project.scripts]
turret = "turret_pi.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["turret_pi"]

[dependency-groups]
dev = [
    "pytest>=9.1.1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

````markdown
# turret-pi

Pi-side actuator for the pan-tilt tracking turret (ADR-0013). Runs on the Raspberry Pi
only, as a package separate from `object_tracker` (different runtime host, disjoint
dependency graph — see `docs/adr/0013-pan-tilt-turret-as-actuator-sink.md`).

Currently ships only the hardware-free pure units (`servo.ServoAngles`/`clamp_angles`,
`wire.decode`). The real I²C `ServoDriver`, the MJPEG streamer, the UDP command listener,
and `main.py` are a follow-up once Phase 0 hardware bring-up has picked a concrete HAT SDK.

## Setup

```bash
uv sync
uv run pytest
```
````

(save the above as `turret/README.md`)

- [ ] **Step 2: Create the package marker**

```python
# turret/turret_pi/__init__.py
"""turret_pi — Pi-side actuator for the pan-tilt tracking turret (ADR-0013).

Runs on the Raspberry Pi only, as a separate installable package from ``object_tracker``
(different runtime host, disjoint dependency graph, different deploy lifecycle). This
package currently ships only the hardware-free pure units (``servo.ServoAngles`` /
``clamp_angles``, ``wire.decode``); the real I2C ``ServoDriver`` and the
streamer/listener/main entrypoint are a follow-up once Phase 0 hardware bring-up has settled
on a concrete HAT SDK.
"""

from __future__ import annotations
```

- [ ] **Step 3: Write the failing test**

```python
# turret/tests/test_servo.py
from __future__ import annotations

from turret_pi.servo import ServoAngles, clamp_angles


def test_clamp_within_range_is_unchanged():
    assert clamp_angles(ServoAngles(90.0, 45.0)) == ServoAngles(90.0, 45.0)


def test_clamp_pan_above_max():
    assert clamp_angles(ServoAngles(200.0, 45.0)) == ServoAngles(180.0, 45.0)


def test_clamp_pan_below_min():
    assert clamp_angles(ServoAngles(-10.0, 45.0)) == ServoAngles(0.0, 45.0)


def test_clamp_tilt_above_max():
    assert clamp_angles(ServoAngles(90.0, 250.0)) == ServoAngles(90.0, 180.0)


def test_clamp_tilt_below_min():
    assert clamp_angles(ServoAngles(90.0, -50.0)) == ServoAngles(90.0, 0.0)
```

- [ ] **Step 4: Install the package and run the test to verify it fails**

Run: `cd turret && uv sync && uv run pytest tests/test_servo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'turret_pi.servo'`

- [ ] **Step 5: Write the implementation**

```python
# turret/turret_pi/servo.py
"""Servo angles (ADR-0013 roadmap Phase 1): the pure, hardware-free half of the servo
driver — ``ServoAngles`` plus mechanical-limit clamping. The real I2C ``ServoDriver`` (the
HAT/PCA9685 I/O) is a follow-up once Phase 0 hardware bring-up picks a concrete SDK; nothing
here depends on that choice.
"""

from __future__ import annotations

from dataclasses import dataclass

# Mechanical limits (deg) for the Waveshare Pan-Tilt HAT's servos — clamped in software so a
# stray command never stalls or strips a servo (roadmap Phase 1 gotcha).
PAN_MIN_DEG = 0.0
PAN_MAX_DEG = 180.0
TILT_MIN_DEG = 0.0
TILT_MAX_DEG = 180.0


@dataclass(frozen=True)
class ServoAngles:
    """An absolute pan/tilt pose in degrees."""

    pan_deg: float
    tilt_deg: float


def clamp_angles(angles: ServoAngles) -> ServoAngles:
    """Clamp both axes to the HAT's mechanical limits (pure, hardware-free)."""
    return ServoAngles(
        pan_deg=max(PAN_MIN_DEG, min(PAN_MAX_DEG, angles.pan_deg)),
        tilt_deg=max(TILT_MIN_DEG, min(TILT_MAX_DEG, angles.tilt_deg)),
    )
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd turret && uv run pytest tests/test_servo.py -v`
Expected: PASS (5 passed)

- [ ] **Step 7: Commit**

```bash
git add turret/pyproject.toml turret/README.md turret/turret_pi/__init__.py turret/turret_pi/servo.py turret/tests/test_servo.py
git commit -m "feat: scaffold turret-pi package with pure ServoAngles/clamp_angles (ADR-0013)"
```

---

### Task 7: Wire protocol — Pi-side decode

**Files:**
- Create: `turret/turret_pi/wire.py`
- Test: `turret/tests/test_wire.py`

**Interfaces:**
- Consumes: nothing (independent of the Mac-side `wire.py` per Global Constraints — no
  shared module).
- Produces: `decode(payload: bytes) -> tuple[float, float, int]` — the `(pan_delta,
  tilt_delta, seq)` tuple the (future, out-of-scope) `listener.run_listener` will consume.

- [ ] **Step 1: Write the failing tests**

```python
# turret/tests/test_wire.py
from __future__ import annotations

import json

import pytest

from turret_pi.wire import decode


def test_decode_round_trips_a_valid_payload():
    payload = json.dumps({"pan_delta": -2.3, "tilt_delta": 0.8, "seq": 1042}).encode("utf-8")
    assert decode(payload) == (-2.3, 0.8, 1042)


def test_decode_raises_value_error_on_garbage_bytes():
    with pytest.raises(ValueError):
        decode(b"not json at all")


def test_decode_raises_value_error_on_missing_field():
    payload = json.dumps({"pan_delta": 1.0, "seq": 1}).encode("utf-8")  # tilt_delta missing
    with pytest.raises(ValueError):
        decode(payload)


def test_decode_raises_value_error_on_non_numeric_field():
    payload = json.dumps({"pan_delta": "abc", "tilt_delta": 0.0, "seq": 1}).encode("utf-8")
    with pytest.raises(ValueError):
        decode(payload)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd turret && uv run pytest tests/test_wire.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'turret_pi.wire'`

- [ ] **Step 3: Write the implementation**

```python
# turret/turret_pi/wire.py
"""Wire protocol — Pi-side half (ADR-0013). Decodes the same JSON-per-UDP-datagram shape
``object_tracker.turret_sink.wire.encode`` produces. No shared module between Mac and Pi
(separate deployables/deps) — this is an independent decode of the documented shape, not an
import of the Mac-side encoder.
"""

from __future__ import annotations

import json


def decode(payload: bytes) -> tuple[float, float, int]:
    """Decode one Aim Command datagram to ``(pan_delta, tilt_delta, seq)``.

    Raises ``ValueError`` on anything that isn't the documented shape (malformed JSON,
    missing/non-numeric fields) — the caller (the future ``listener.run_listener``) drops
    such a datagram rather than propagating a crash from a single bad packet.
    """
    try:
        obj = json.loads(payload)
        return float(obj["pan_delta"]), float(obj["tilt_delta"]), int(obj["seq"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"malformed aim command payload: {payload!r}") from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd turret && uv run pytest tests/test_wire.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add turret/turret_pi/wire.py turret/tests/test_wire.py
git commit -m "feat: add turret_pi wire decode (ADR-0013)"
```

---

### Task 8: Widen `FrameSink` with an optional `tracks` parameter

**Files:**
- Modify: `object_tracker/sinks.py`
- Test: `tests/test_sinks.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `FrameSink.show(self, frame: np.ndarray, tracks: sv.Detections | None = None) ->
  bool` — the widened Protocol every sink (including the future `ActuatorSink`) implements;
  `pipeline.py` (Task 9) is the sole caller that passes a real `tracks` value.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_sinks.py` (add `import supervision as sv` to its imports at the top,
alongside the existing `import numpy as np` / `import pytest`):

```python
def test_window_sink_show_accepts_a_tracks_argument(monkeypatch):
    _patch_window(monkeypatch, key=-1, visible=1.0)
    assert WindowSink().show(_frame(), sv.Detections.empty()) is True


def test_composite_forwards_tracks_to_every_child():
    a, b = FakeSink(), FakeSink()
    composite = CompositeSink([a, b])
    tracks = sv.Detections.empty()

    composite.show(_frame(), tracks)

    assert a.tracks_received == [tracks]
    assert b.tracks_received == [tracks]
```

Also widen the existing `FakeSink` double so it records what it was given (replace its
`show` method):

```python
class FakeSink:
    def __init__(self, *, show_result=True, raise_on_close=False):
        self.shown: list[np.ndarray] = []
        self.tracks_received: list = []
        self.closed = 0
        self._show_result = show_result
        self._raise_on_close = raise_on_close

    def show(self, frame: np.ndarray, tracks=None) -> bool:
        self.shown.append(frame)
        self.tracks_received.append(tracks)
        return self._show_result

    def close(self) -> None:
        self.closed += 1
        if self._raise_on_close:
            raise RuntimeError("close failed")
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `uv run pytest tests/test_sinks.py -v`
Expected: FAIL — `test_window_sink_show_accepts_a_tracks_argument` fails with `TypeError:
show() takes 2 positional arguments but 3 were given`; `test_composite_forwards_tracks_to_every_child`
fails the same way once `CompositeSink.show` is called with two args.

- [ ] **Step 3: Widen `FrameSink` and every implementation**

In `object_tracker/sinks.py`, add `import supervision as sv` is already present; widen each
signature:

```python
class FrameSink(Protocol):
    """A destination for annotated frames.

    ``show`` returns ``False`` to ask the loop to stop (e.g. the viewer pressed ``q``);
    ``True`` to continue. ``tracks`` carries the frame's confirmed Tracks under ``--track``
    (``None`` otherwise) — sinks that don't need it (``VideoFileSink``, ``WindowSink``)
    ignore it; the Actuator Sink is why it exists. ``close`` frees any underlying
    writer/window.
    """

    def show(self, frame: np.ndarray, tracks: sv.Detections | None = None) -> bool: ...

    def close(self) -> None: ...
```

```python
class VideoFileSink:
    ...
    def show(self, frame: np.ndarray, tracks: sv.Detections | None = None) -> bool:
        self._sink.write_frame(frame)
        return True
```

```python
class WindowSink:
    ...
    def show(self, frame: np.ndarray, tracks: sv.Detections | None = None) -> bool:
        cv2.imshow(self._window_name, frame)
        if (cv2.waitKey(1) & 0xFF) == ord("q"):
            return False
        if cv2.getWindowProperty(self._window_name, cv2.WND_PROP_VISIBLE) < 1:
            return False
        return True
```

```python
class CompositeSink:
    """A ``FrameSink`` that fans one frame out to several sinks (``--record`` = window+file,
    or ``--record`` + ``--turret`` = window+file+actuator).

    ``show`` calls **every** child (no short-circuit) and returns the logical AND of their
    results, forwarding ``tracks`` to each unchanged.
    """

    def __init__(self, sinks: list[FrameSink]) -> None:
        self._sinks = list(sinks)

    def show(self, frame: np.ndarray, tracks: sv.Detections | None = None) -> bool:
        keep_going = True
        for sink in self._sinks:
            if not sink.show(frame, tracks):
                keep_going = False
        return keep_going

    def close(self) -> None:
        first_error: Exception | None = None
        for sink in self._sinks:
            try:
                sink.close()
            except Exception as exc:  # noqa: BLE001 - close the rest, surface one failure
                first_error = first_error or exc
        if first_error is not None:
            raise first_error
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_sinks.py -v`
Expected: PASS (all sinks tests, including the two new ones)

- [ ] **Step 5: Commit**

```bash
git add object_tracker/sinks.py tests/test_sinks.py
git commit -m "feat: widen FrameSink.show with an optional tracks parameter (ADR-0013)"
```

---

### Task 9: Thread confirmed Tracks through `pipeline.run`

**Files:**
- Modify: `object_tracker/pipeline.py`
- Test: `tests/test_io.py`

**Interfaces:**
- Consumes: the widened `FrameSink.show(frame, tracks=None)` (Task 8).
- Produces: no new function — `pipeline.run`'s only behavior change is passing `tracks` to
  `sink.show(...)`; `tracks` is the real `confirmed` Detections under `--track`, `None`
  otherwise. `pipeline.run()`'s own parameter list is unchanged (Global Constraints).

- [ ] **Step 1: Write the failing tests**

In `tests/test_io.py`, widen `RecordingSink` to record what it was given (replace it):

```python
class RecordingSink:
    """A ``FrameSink`` that records shown frames + tracks; stops after ``stop_after`` shows."""

    def __init__(self, stop_after: int | None = None) -> None:
        self.shown: list[np.ndarray] = []
        self.shown_tracks: list = []
        self.closed = 0
        self._stop_after = stop_after

    def show(self, frame: np.ndarray, tracks=None) -> bool:
        self.shown.append(frame)
        self.shown_tracks.append(tracks)
        if self._stop_after is not None and len(self.shown) >= self._stop_after:
            return False
        return True

    def close(self) -> None:
        self.closed += 1
```

Add two new tests (near `test_run_track_path_calls_track_and_records_id`):

```python
def test_run_track_path_passes_confirmed_tracks_to_sink():
    source = FakeSource(_frames(2), _info(2))
    sink = RecordingSink()

    run(StubTrackingDetector(), source, sink, _NO_ZOOM, _TRACK, sidecar_path=None)

    assert len(sink.shown_tracks) == 2
    for tracks in sink.shown_tracks:
        assert tracks is not None
        assert list(tracks.tracker_id) == [7]


def test_run_no_track_path_passes_none_tracks():
    source = FakeSource(_frames(2), _info(2))
    sink = RecordingSink()

    run(StubDetector(), source, sink, _NO_ZOOM, _NO_TRACK, sidecar_path=None)

    assert sink.shown_tracks == [None, None]
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `uv run pytest tests/test_io.py -v`
Expected: FAIL — both new tests fail with `AttributeError: 'RecordingSink' object has no
attribute 'shown_tracks'` is already fixed by the `RecordingSink` edit above, so instead they
fail on the assertion itself (`sink.shown_tracks` is all `None` even under `--track`,
because `pipeline.run` doesn't pass `tracks` yet).

- [ ] **Step 3: Thread `tracks` through the loop**

In `object_tracker/pipeline.py`, add the import and widen the loop body:

```python
import supervision as sv  # add alongside the existing imports
```

Replace the loop body (`object_tracker/pipeline.py:62-84`) with:

```python
        for idx, frame in enumerate(tqdm(source, total=info.total_frames, unit="f")):
            ts = time.time() if is_live else None
            tracks: sv.Detections | None = None
            if rt is not None and tracking_detector is not None:
                confirmed = tracking_detector.track(frame)
                tracks = confirmed
                records = detection_records(confirmed, with_track_id=True)
                annotated = _annotate_confirmed(frame, confirmed, rt.ann)
                if rt.slots is not None:
                    renders = rt.slots.update(_present_centers(confirmed), idx)
                    annotated = draw_identity_panels(
                        annotated, frame, renders, zoom.size, frame_wh, rt.slots.capacity
                    )
            else:
                detections = detector.detect(frame)
                records = detection_records(detections)
                annotated = detection_annotator.annotate(scene=frame.copy(), detections=detections)
                if zoom.enabled:
                    zoom_center = _confidence_zoom(
                        annotated, frame, detections, zoom, frame_wh, zoom_center
                    )
            if sidecar is not None:
                sidecar.write(json.dumps(frame_record(idx, records, ts)) + "\n")
            if not sink.show(annotated, tracks):
                break
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_io.py -v`
Expected: PASS (all `test_io.py` tests, including the two new ones)

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS (no regressions elsewhere)

- [ ] **Step 6: Commit**

```bash
git add object_tracker/pipeline.py tests/test_io.py
git commit -m "feat: thread confirmed Tracks through pipeline.run to sink.show (ADR-0013)"
```

---

### Task 10: `ActuatorSink` — the FrameSink that aims the turret

**Files:**
- Create: `object_tracker/turret_sink/actuator_sink.py`
- Test: `tests/test_actuator_sink.py`

**Interfaces:**
- Consumes: `AimGains` (Task 1), `_present_centers` from `object_tracker.tracking` (existing),
  `select_target` (Task 2), `AimControllerState`/`step` (Task 3), `AimTransport` (Task 5),
  the widened `FrameSink` shape (Task 8).
- Produces: `ActuatorSink(transport: AimTransport, gains: AimGains, frame_wh: tuple[int,
  int])` implementing `FrameSink` — consumed by `cli.py`'s `_maybe_add_turret` (Task 12).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_actuator_sink.py
"""Unit tests for ActuatorSink (ADR-0013) — the FrameSink that aims the turret.

Uses a fake AimTransport double (mirrors FakeSink in tests/test_sinks.py) so no real
socket/hardware is touched.
"""

from __future__ import annotations

import numpy as np
import supervision as sv

from object_tracker.config import AimGains, COCO_BIRD_CLASS_ID
from object_tracker.turret_sink.actuator_sink import ActuatorSink
from object_tracker.turret_sink.aim_controller import AimCommand


class FakeTransport:
    def __init__(self):
        self.sent: list[AimCommand] = []
        self.closed = 0

    def send(self, command):
        self.sent.append(command)

    def close(self):
        self.closed += 1


def _tracked(tracker_ids, boxes):
    return sv.Detections(
        xyxy=np.asarray(boxes, dtype=float),
        class_id=np.asarray([COCO_BIRD_CLASS_ID] * len(boxes)),
        tracker_id=np.asarray(tracker_ids),
    )


def _gains():
    return AimGains(kp=0.1, deadzone_px=0.0, max_delta_deg=100.0)


FRAME_WH = (100, 50)  # centre = (50.0, 25.0)


def _blank_frame():
    return np.zeros((50, 100, 3), dtype=np.uint8)


def test_show_sends_no_command_when_no_tracks():
    transport = FakeTransport()
    sink = ActuatorSink(transport, _gains(), FRAME_WH)

    assert sink.show(_blank_frame(), None) is True
    assert transport.sent == []


def test_show_locks_and_sends_a_command_for_the_first_seen_id():
    transport = FakeTransport()
    sink = ActuatorSink(transport, _gains(), FRAME_WH)
    tracks = _tracked([5], [[60, 20, 80, 30]])  # centre (70, 25) -> error (20, 0)

    sink.show(_blank_frame(), tracks)

    assert len(transport.sent) == 1
    assert transport.sent[0].pan_delta > 0.0  # target right of centre -> pan right (+)


def test_show_keeps_the_lock_when_a_second_id_appears():
    transport = FakeTransport()
    sink = ActuatorSink(transport, _gains(), FRAME_WH)

    sink.show(_blank_frame(), _tracked([5], [[60, 20, 80, 30]]))  # locks 5 (right of centre)
    sink.show(
        _blank_frame(),
        _tracked([5, 9], [[60, 20, 80, 30], [0, 0, 10, 10]]),  # 9 is left of centre
    )

    # still locked on 5 (right of centre) -> pan stays positive, not the negative 9 would give
    assert transport.sent[-1].pan_delta > 0.0


def test_show_holds_position_and_relatches_after_losing_the_locked_id():
    transport = FakeTransport()
    sink = ActuatorSink(transport, _gains(), FRAME_WH)

    sink.show(_blank_frame(), _tracked([5], [[60, 20, 80, 30]]))  # locks 5, sends a command
    sent_after_first = len(transport.sent)

    sink.show(_blank_frame(), sv.Detections.empty())  # 5 is gone -> holds, no command
    assert len(transport.sent) == sent_after_first

    sink.show(_blank_frame(), _tracked([9], [[0, 0, 10, 10]]))  # re-latches onto 9
    assert len(transport.sent) == sent_after_first + 1
    assert transport.sent[-1].pan_delta < 0.0  # 9's centre (5,5) is left of frame centre (50,25)


def test_close_closes_the_transport():
    transport = FakeTransport()
    ActuatorSink(transport, _gains(), FRAME_WH).close()
    assert transport.closed == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_actuator_sink.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'object_tracker.turret_sink.actuator_sink'`

- [ ] **Step 3: Write the implementation**

```python
# object_tracker/turret_sink/actuator_sink.py
"""Actuator Sink (ADR-0013): the FrameSink that aims the turret instead of drawing.

Glue only — pulls the frame's Track centres, threads Target Selector + Aim Controller, and
ships the resulting Aim Command down the configured AimTransport. Mirrors the existing
sinks.py shape: a thin, stateful wrapper around pure functions, the same
pure-step-wrapped-in-a-stateful-manager pattern zoom.py's ZoomSlots already uses.
"""

from __future__ import annotations

import time

import numpy as np
import supervision as sv

from ..config import AimGains
from ..tracking import _present_centers
from .aim_controller import AimControllerState, step
from .target_selector import select_target
from .transport import AimTransport


class ActuatorSink:
    """A FrameSink that never draws; always returns True (never asks the loop to stop)."""

    def __init__(
        self, transport: AimTransport, gains: AimGains, frame_wh: tuple[int, int]
    ) -> None:
        self._transport = transport
        self._gains = gains
        self._center = (frame_wh[0] / 2.0, frame_wh[1] / 2.0)
        self._locked_id: int | None = None
        self._state = AimControllerState()
        self._last_ts: float | None = None

    def show(self, frame: np.ndarray, tracks: sv.Detections | None = None) -> bool:
        present = _present_centers(tracks) if tracks is not None else {}
        self._locked_id = select_target(frozenset(present.keys()), self._locked_id)
        now = time.monotonic()
        dt = 0.0 if self._last_ts is None else max(0.0, now - self._last_ts)
        self._last_ts = now
        if self._locked_id is not None:
            target = present[self._locked_id]
            error = (target[0] - self._center[0], target[1] - self._center[1])
            command, self._state = step(error, self._gains, self._state, dt)
            self._transport.send(command)
        return True

    def close(self) -> None:
        self._transport.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_actuator_sink.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add object_tracker/turret_sink/actuator_sink.py tests/test_actuator_sink.py
git commit -m "feat: add ActuatorSink, the turret's FrameSink (ADR-0013)"
```

---

### Task 11: `turret_sink` package re-exports

**Files:**
- Modify: `object_tracker/turret_sink/__init__.py`
- Test: `tests/test_turret_sink_package.py`

**Interfaces:**
- Consumes: everything created in Tasks 2–5 and 10.
- Produces: the package's public surface, importable from `object_tracker.turret_sink`
  directly — consumed by `cli.py` (Task 12).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_turret_sink_package.py
"""Smoke test: the turret_sink package's public re-exports are importable from its root."""

from __future__ import annotations


def test_public_names_importable_from_package_root():
    from object_tracker import turret_sink

    for name in [
        "ActuatorSink",
        "AimCommand",
        "AimControllerState",
        "step",
        "select_target",
        "AimTransport",
        "UdpAimTransport",
        "encode",
    ]:
        assert hasattr(turret_sink, name), f"{name} not exported from turret_sink"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_turret_sink_package.py -v`
Expected: FAIL — `AttributeError` / `assert False` for every name (the `__init__.py` from
Task 2 exports nothing yet)

- [ ] **Step 3: Fill in the re-exports**

```python
# object_tracker/turret_sink/__init__.py
"""turret_sink — the Mac-side Actuator Sink for the pan-tilt tracking turret (ADR-0013).

Re-exports the package's public surface: pure Target Selector / Aim Controller units, the
UDP wire encode + transport, and the ActuatorSink FrameSink that glues them together.
"""

from __future__ import annotations

from .actuator_sink import ActuatorSink
from .aim_controller import AimCommand, AimControllerState, step
from .target_selector import select_target
from .transport import AimTransport, UdpAimTransport
from .wire import encode

__all__ = [
    "ActuatorSink",
    "AimCommand",
    "AimControllerState",
    "step",
    "select_target",
    "AimTransport",
    "UdpAimTransport",
    "encode",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_turret_sink_package.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add object_tracker/turret_sink/__init__.py tests/test_turret_sink_package.py
git commit -m "feat: export turret_sink's public surface from its package root"
```

---

### Task 12: CLI — `--turret` flags + validation + wiring

**Files:**
- Modify: `object_tracker/cli.py`
- Modify: `docs/cli-cheatsheet.md`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `AimGains`, `TurretConfig`, `DEFAULT_TURRET_KP/KI/KD/DEADZONE_PX/MAX_DELTA_DEG/PORT`
  (Task 1), `ActuatorSink`, `UdpAimTransport` (Task 11's re-exports).
- Produces: `_parse_turret_target(text: str) -> tuple[str, int]`, `_maybe_add_turret(sink:
  FrameSink, args, frame_wh: tuple[int, int]) -> FrameSink`, and `validation_error(...,
  turret: bool = False)` — no other task depends on these; they're wired into `main()`.
  `_maybe_add_turret` is where `TurretConfig` (added but unused in Task 1) gets its one
  consumer: it bundles the parsed host/port/gains before handing them to
  `UdpAimTransport`/`ActuatorSink`, the same way `_build_configs` bundles `DetectConfig`/
  `ZoomConfig`/`TrackConfig` from args elsewhere in this file.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py` (add `_maybe_add_turret` and `_parse_turret_target` to the
existing `from object_tracker.cli import (...)` block, and `DEFAULT_TURRET_KP`,
`DEFAULT_TURRET_KI`, `DEFAULT_TURRET_KD`, `DEFAULT_TURRET_DEADZONE_PX`,
`DEFAULT_TURRET_MAX_DELTA_DEG`, `DEFAULT_TURRET_PORT` to the existing
`from object_tracker.config import (...)` block):

```python
# --- CLI: turret flags --------------------------------------------------------------
def test_turret_defaults_to_none():
    args = build_parser().parse_args(["--source", "x.mp4"])
    assert args.turret is None


def test_turret_parses_host_port():
    args = build_parser().parse_args(["--source", "0", "--turret", "pi.local:9000"])
    assert args.turret == "pi.local:9000"


def test_turret_gain_flags_default_from_config():
    args = build_parser().parse_args(["--source", "x.mp4"])
    assert args.turret_kp == DEFAULT_TURRET_KP
    assert args.turret_ki == DEFAULT_TURRET_KI
    assert args.turret_kd == DEFAULT_TURRET_KD
    assert args.turret_deadzone_px == DEFAULT_TURRET_DEADZONE_PX
    assert args.turret_max_deg == DEFAULT_TURRET_MAX_DELTA_DEG


def test_validation_error_turret_requires_track():
    assert validation_error(0.05, 1, track=False, turret=True) == "--turret requires --track"


def test_validation_error_turret_with_track_is_fine():
    assert validation_error(0.05, 1, track=True, turret=True) is None


def test_parse_turret_target_splits_host_and_port():
    assert _parse_turret_target("pi.local:9000") == ("pi.local", 9000)


def test_parse_turret_target_defaults_port_when_omitted():
    assert _parse_turret_target("pi.local") == ("pi.local", DEFAULT_TURRET_PORT)


def test_parse_turret_target_rejects_empty_host():
    with pytest.raises(ValueError):
        _parse_turret_target(":9000")


def test_parse_turret_target_rejects_non_numeric_port():
    with pytest.raises(ValueError):
        _parse_turret_target("pi.local:abc")


class _FakeTurretArgs:
    turret = "pi.local:9000"
    turret_kp = 0.1
    turret_ki = 0.0
    turret_kd = 0.0
    turret_deadzone_px = 5.0
    turret_max_deg = 5.0


def test_maybe_add_turret_wraps_sink_in_composite(monkeypatch):
    from object_tracker.sinks import CompositeSink

    created = {}

    class FakeUdpTransport:
        def __init__(self, host, port):
            created["host"] = host
            created["port"] = port

        def send(self, command):
            pass

        def close(self):
            pass

    monkeypatch.setattr(cli, "UdpAimTransport", FakeUdpTransport)

    base_sink = object()  # stand-in FrameSink; never called in this test
    result = cli._maybe_add_turret(base_sink, _FakeTurretArgs(), (640, 480))

    assert isinstance(result, CompositeSink)
    assert created == {"host": "pi.local", "port": 9000}


def test_maybe_add_turret_passthrough_when_no_turret():
    class _NoTurretArgs(_FakeTurretArgs):
        turret = None

    base_sink = object()
    assert cli._maybe_add_turret(base_sink, _NoTurretArgs(), (640, 480)) is base_sink
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — `AttributeError: module 'object_tracker.cli' has no attribute
'_maybe_add_turret'` (and `ImportError` on `DEFAULT_TURRET_KP` etc. until the import line is
also added, which happens together with Step 1 in the same edit)

- [ ] **Step 3: Add the config imports and turret flags to `build_parser`**

In `object_tracker/cli.py`, widen the `from .config import (...)` block (`cli.py:25-39`) to
add `AimGains`, `TurretConfig`, `DEFAULT_TURRET_KP`, `DEFAULT_TURRET_KI`,
`DEFAULT_TURRET_KD`, `DEFAULT_TURRET_DEADZONE_PX`, `DEFAULT_TURRET_MAX_DELTA_DEG`,
`DEFAULT_TURRET_PORT`, and add a new import line:

```python
from .turret_sink import ActuatorSink, UdpAimTransport
```

Add the turret flags to `build_parser`, right before the final `return p` (after the
existing `--record` argument, `cli.py:187-188`):

```python
    p.add_argument("--turret", default=None, metavar="HOST[:PORT]",
                   help="Live only, requires --track: also aim a pan-tilt turret via UDP "
                        f"Aim Commands (default port {DEFAULT_TURRET_PORT}; ADR-0013)")
    p.add_argument("--turret-kp", type=float, default=DEFAULT_TURRET_KP,
                   help="Aim Controller proportional gain (deg per px error)")
    p.add_argument("--turret-ki", type=float, default=DEFAULT_TURRET_KI,
                   help="Aim Controller integral gain (0.0 = P-only, Phase 3)")
    p.add_argument("--turret-kd", type=float, default=DEFAULT_TURRET_KD,
                   help="Aim Controller derivative gain (0.0 = P-only, Phase 3)")
    p.add_argument("--turret-deadzone-px", type=float, default=DEFAULT_TURRET_DEADZONE_PX,
                   help="Pixel error below this is treated as zero (jitter floor)")
    p.add_argument("--turret-max-deg", type=float, default=DEFAULT_TURRET_MAX_DELTA_DEG,
                   help="Per-step slew clamp on a single Aim Command (deg)")
```

- [ ] **Step 4: Widen `validation_error` and add the two helpers**

Widen `validation_error` (`cli.py:124-141`):

```python
def validation_error(
    zoom_size: float,
    zoom_max: int,
    *,
    track: bool = True,
    track_buffer: int = DEFAULT_TRACK_BUFFER,
    zoom_track_id: int | None = None,
    turret: bool = False,
) -> str | None:
    """Return a user-facing message for an invalid arg combination, else ``None``."""
    if not 0.0 < zoom_size <= 1.0:
        return "--zoom-size must be in (0, 1]"
    if zoom_max < 1:
        return "--zoom-max must be >= 1"
    if track_buffer < 1:
        return "--track-buffer must be >= 1"
    if zoom_track_id is not None and not track:
        return "--zoom-track-id requires --track (it can't follow an id with --no-track)"
    if turret and not track:
        return "--turret requires --track"
    return None
```

Add the two new helpers near `_derive_paths`/`_resolve_classes` (top of `cli.py`, after the
imports):

```python
def _parse_turret_target(text: str) -> tuple[str, int]:
    """Parse ``--turret HOST[:PORT]`` (pure); PORT defaults to ``DEFAULT_TURRET_PORT`` when
    omitted. Raises ``ValueError`` on a malformed target (empty host, non-numeric port)."""
    host, sep, port_text = text.rpartition(":")
    if not sep:
        return text, DEFAULT_TURRET_PORT
    if not host or not port_text.isdigit():
        raise ValueError(f"--turret target must be HOST[:PORT], got {text!r}")
    return host, int(port_text)


def _maybe_add_turret(sink: FrameSink, args, frame_wh: tuple[int, int]) -> FrameSink:
    """Fold an Actuator Sink into ``sink`` when ``--turret`` is given, else return it as-is."""
    if args.turret is None:
        return sink
    host, port = _parse_turret_target(args.turret)
    turret = TurretConfig(
        host=host,
        port=port,
        gains=AimGains(
            kp=args.turret_kp,
            ki=args.turret_ki,
            kd=args.turret_kd,
            deadzone_px=args.turret_deadzone_px,
            max_delta_deg=args.turret_max_deg,
        ),
    )
    actuator = ActuatorSink(UdpAimTransport(turret.host, turret.port), turret.gains, frame_wh)
    return CompositeSink([sink, actuator])
```

- [ ] **Step 5: Wire `main()` — Live-only check, validation call, sink wiring, status line**

Add a Live-only check next to the existing `--record` one (`cli.py:227-230`):

```python
    if args.turret is not None and not is_live:
        print("error: --turret is Live-only (the turret aims a live camera feed)",
              file=sys.stderr)
        return 1
```

Pass `turret=args.turret is not None` into the `validation_error(...)` call (`cli.py:239-245`):

```python
    err = validation_error(
        args.zoom_size,
        args.zoom_max,
        track=track_on,
        track_buffer=args.track_buffer,
        zoom_track_id=args.zoom_track_id,
        turret=args.turret is not None,
    )
```

Fold the Actuator Sink in right after `_select_source_sink` succeeds (`cli.py:255-259`):

```python
    try:
        frame_source, sink, sidecar_path, written, source_label = _select_source_sink(spec, args)
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    sink = _maybe_add_turret(sink, args, frame_source.info.resolution_wh)
```

Add turret status to the existing status-line `print(...)` (`cli.py:263-269`), appending one
more concatenated piece:

```python
    print(f"mode={'live' if is_live else 'offline'} source={source_label} "
          f"device={cfg.device} slicing={'on' if slicing_on else 'off'} "
          f"conf={cfg.conf} classes={cfg.classes if cfg.classes is not None else 'all'} "
          f"track={'on' if track.enabled else 'off'} "
          + (f"tracker={track.tracker.name.lower()} " if track.enabled else "")
          + f"zoom={'on' if zoom.enabled else 'off'} zoom_max={zoom.max_panels}"
          + (f" zoom_track_id={zoom.track_id}" if zoom.track_id is not None else "")
          + (f" turret={args.turret}" if args.turret is not None else ""))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS (all `test_cli.py` tests, including the new turret ones)

- [ ] **Step 7: Update the CLI cheat sheet**

In `docs/cli-cheatsheet.md`, add a row to the existing "Outputs" table:

```markdown
| `--turret` | — | **Live only, requires `--track`** — also aim a pan-tilt turret via UDP Aim Commands to `HOST[:PORT]` (port defaults to `9000`; ADR-0013) |
```

And add a new table after "Zoom & track knobs":

```markdown
### Turret knobs (only matter with `--turret`)
| Flag | Default | Notes |
| --- | --- | --- |
| `--turret-kp` | `0.05` | Aim Controller proportional gain (deg per px error) |
| `--turret-ki` | `0.0` | Integral gain — `0.0` is P-only (Phase 3); nonzero is PID (Phase 4) |
| `--turret-kd` | `0.0` | Derivative gain — ditto |
| `--turret-deadzone-px` | `6.0` | Pixel error below this is treated as zero (kills jitter at rest) |
| `--turret-max-deg` | `5.0` | Per-step slew clamp on a single Aim Command |
```

- [ ] **Step 8: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS (no regressions)

- [ ] **Step 9: Commit**

```bash
git add object_tracker/cli.py docs/cli-cheatsheet.md tests/test_cli.py
git commit -m "feat: add --turret CLI flags and Actuator Sink wiring (ADR-0013)"
```

---

### Task 13: Full verification

**Files:** none (verification only)

**Interfaces:** none

- [ ] **Step 1: Run the full Mac-side suite**

Run: `uv run pytest -v`
Expected: PASS — every test from Tasks 1–12, plus the pre-existing suite, green.

- [ ] **Step 2: Run the turret-pi suite**

Run: `cd turret && uv run pytest -v`
Expected: PASS — `test_servo.py` (5) + `test_wire.py` (4).

- [ ] **Step 3: Manually sanity-check the CLI help text**

Run: `uv run track --help`
Expected: `--turret`, `--turret-kp`, `--turret-ki`, `--turret-kd`, `--turret-deadzone-px`,
`--turret-max-deg` all appear with the help text written in Task 12.

- [ ] **Step 4: Manually sanity-check `--turret` without `--track` is rejected**

Run: `uv run track --source 0 --turret 127.0.0.1:9000 --no-track`
Expected: prints `error: --turret requires --track` to stderr and exits non-zero.

- [ ] **Step 5: Checkpoint**

Confirm no uncommitted changes remain:

```bash
git status
```

Expected: clean (everything committed task-by-task above). This plan's scope ends here —
the Pi-side `ServoDriver`/`streamer.py`/`listener.py`/`main.py` are a follow-up plan, written
once Phase 0 hardware bring-up (SSH, venv, `raspi-config` I²C) is done on the physical Pi and
a concrete HAT SDK is chosen.
