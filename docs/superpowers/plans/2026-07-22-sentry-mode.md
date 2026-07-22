# Sentry Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the Actuator Sink has no locked Track for 2 s, sweep the turret's pan axis 0–180° (triangle wave, 15 °/s, first direction left) and relocate tilt to a default patrol angle, until a target appears — then hand back to tracking on the very next frame.

**Architecture:** A new pure state machine `object_tracker/turret_sink/sentry.py` (frozen dataclass threaded through pure functions, mirroring `aim_controller.py`) dead-reckons the absolute pan/tilt pose by accumulating every delta the host ships. `ActuatorSink.show` grows an unlocked branch that calls it. No Pi changes, no wire changes (spec: `docs/superpowers/specs/2026-07-22-sentry-mode-design.md`).

**Tech Stack:** Python 3.12, frozen dataclasses, pytest (AAA style), numpy/supervision only in the sink tests (never in `sentry.py`).

## Global Constraints

- TDD is mandatory: every task writes its failing tests first, sees them fail, then implements (repo rule `.claude/rules/ecc/common/testing.md`).
- `sentry.py` must stay pure: no sockets, no hardware, no `time` module, no numpy — time arrives as explicit `dt`.
- All new dataclasses are `@dataclass(frozen=True)`; never mutate, always return new instances.
- Constants, not CLI flags. All tuning values live in `object_tracker/config.py` (including `SENTRY_TILT_DEFAULT_DEG = 90.0`, already added there).
- `turret/turret_pi/*`, `wire.py`, `transport.py`, `target_selector.py`, `aim_controller.py`, `pipeline.py`, and the CLI surface are **unchanged**.
- Host-side clamp constants mirror `turret/turret_pi/servo.py` (`PAN 0–180`, `TILT 20–115`, `CENTER = pan 90.0 / tilt 67.5`) but share no module with it — a comment on each side points at the other.
- Commit format: `<type>: <description>` (conventional commits, no attribution trailer).
- Run tests from the repo root: `python -m pytest tests/<file> -v` (or plain `pytest`).

**Spec correction (fold into Task 1):** the spec's dead-reckoning section says the Pi "recenters to `CENTER` (90/90)". Reality (`turret/turret_pi/servo.py:45-48`): `CENTER` is pan 90.0, tilt **67.5** (`(20 + 115) / 2`). Task 1 fixes the spec line and the estimates start at 90.0 / 67.5.

## File Structure

- `object_tracker/config.py` — add sentry constants block + frozen `SentryConfig` (modify; constant `SENTRY_TILT_DEFAULT_DEG` already present).
- `object_tracker/turret_sink/sentry.py` — **new**: `SentryState`, `observe_aim`, `step`. Pure functions only.
- `object_tracker/turret_sink/actuator_sink.py` — modify: unlocked branch + injectable clock.
- `tests/test_sentry.py` — **new**: one test per spec invariant.
- `tests/test_actuator_sink.py` — extend: sentry behaviour through the sink.
- `docs/superpowers/specs/2026-07-22-sentry-mode-design.md` — modify: the 90/90 correction (Task 1 only).

---

### Task 1: Sentry config + grace-period skeleton

**Files:**
- Modify: `object_tracker/config.py` (after the turret block, lines ~66-75)
- Create: `object_tracker/turret_sink/sentry.py`
- Create: `tests/test_sentry.py`
- Modify: `docs/superpowers/specs/2026-07-22-sentry-mode-design.md` (the "(90/90)" line / "Both start at 90.0°" bullet)

**Interfaces:**
- Consumes: `DEFAULT_TURRET_MAX_DELTA_DEG` (5.0) from `config.py`.
- Produces (later tasks rely on these exact names):
  - `config.SentryConfig` frozen dataclass, fields: `grace_s: float = 2.0`, `speed_deg_s: float = 15.0`, `pan_min_deg: float = 0.0`, `pan_max_deg: float = 180.0`, `tilt_min_deg: float = 20.0`, `tilt_max_deg: float = 115.0`, `tilt_default_deg: float = 90.0`, `max_delta_deg: float = 5.0`
  - `sentry.SentryState` frozen dataclass, fields: `pan_estimate_deg: float = 90.0`, `tilt_estimate_deg: float = 67.5`, `direction: float = -1.0`, `unlocked_for_s: float = 0.0`
  - `sentry.step(state: SentryState, dt: float, config: SentryConfig) -> tuple[float, float, SentryState]` returning `(pan_delta, tilt_delta, new_state)`

- [ ] **Step 1: Write the failing tests** — create `tests/test_sentry.py`:

```python
"""Unit tests for the sentry state machine (sentry design 2026-07-22).

Pure functions — no hardware, no sockets; time is faked via explicit ``dt``.
One test per spec invariant, AAA style.
"""

from __future__ import annotations

from object_tracker.config import SentryConfig
from object_tracker.turret_sink.sentry import SentryState, step

CFG = SentryConfig()  # grace 2.0 s, 15 deg/s, pan 0-180, tilt 20-115, default 90, max_delta 5


def test_no_output_while_below_grace_period():
    state = SentryState()

    pan, tilt, state = step(state, dt=1.0, config=CFG)  # unlocked_for 1.0 <= 2.0

    assert (pan, tilt) == (0.0, 0.0)
    assert state.unlocked_for_s == 1.0


def test_output_begins_on_the_frame_that_crosses_grace():
    state = SentryState()
    _, _, state = step(state, dt=1.0, config=CFG)  # 1.0 — silent
    _, _, state = step(state, dt=1.0, config=CFG)  # 2.0 — still not > grace, silent

    pan, tilt, state = step(state, dt=0.1, config=CFG)  # 2.1 > 2.0 — sweep starts

    assert pan != 0.0


def test_dt_zero_emits_no_motion():
    state = SentryState(unlocked_for_s=10.0)  # far past grace

    pan, tilt, new_state = step(state, dt=0.0, config=CFG)

    assert (pan, tilt) == (0.0, 0.0)
    assert new_state.pan_estimate_deg == state.pan_estimate_deg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sentry.py -v`
Expected: FAIL / collection ERROR with `ImportError: cannot import name 'SentryConfig'` (and the `sentry` module not existing).

- [ ] **Step 3: Add the config block** — in `object_tracker/config.py`, replace the existing two-line sentry section (`# --- sentry mode ...` + `SENTRY_TILT_DEFAULT_DEG = 90.0 ...`) with:

```python
# --- sentry mode (2026-07-22 design) — no-target pan sweep for the Actuator Sink -----
SENTRY_GRACE_S = 2.0  # unlocked time before the sweep starts
SENTRY_SPEED_DEG_S = 15.0  # continuous sweep speed (pan sweep AND tilt relocation)
SENTRY_PAN_MIN_DEG = 0.0  # mirrors turret/turret_pi/servo.py PAN_MIN_DEG (no shared module)
SENTRY_PAN_MAX_DEG = 180.0  # mirrors turret/turret_pi/servo.py PAN_MAX_DEG
SENTRY_TILT_MIN_DEG = 20.0  # mirrors turret/turret_pi/servo.py TILT_MIN_DEG
SENTRY_TILT_MAX_DEG = 115.0  # mirrors turret/turret_pi/servo.py TILT_MAX_DEG
SENTRY_TILT_DEFAULT_DEG = 90.0  # patrol tilt the no-target sweep relocates to and holds
```

And add this dataclass next to `AimGains` (before `TurretConfig`):

```python
@dataclass(frozen=True)
class SentryConfig:
    """Sentry-mode tuning (2026-07-22 design): grace, sweep speed, and the host-side
    mirrors of the Pi's servo clamps. ``max_delta_deg`` reuses the turret's per-step
    slew clamp so a pipeline stall can't produce a violent sweep jump."""

    grace_s: float = SENTRY_GRACE_S
    speed_deg_s: float = SENTRY_SPEED_DEG_S
    pan_min_deg: float = SENTRY_PAN_MIN_DEG
    pan_max_deg: float = SENTRY_PAN_MAX_DEG
    tilt_min_deg: float = SENTRY_TILT_MIN_DEG
    tilt_max_deg: float = SENTRY_TILT_MAX_DEG
    tilt_default_deg: float = SENTRY_TILT_DEFAULT_DEG
    max_delta_deg: float = DEFAULT_TURRET_MAX_DELTA_DEG
```

- [ ] **Step 4: Create `object_tracker/turret_sink/sentry.py`** — write `step` complete now (Tasks 2–3 then only add verifying tests; the function is small enough that splitting the implementation would produce throwaway stubs):

```python
"""Sentry state machine (2026-07-22 design): no-target pan sweep with dead-reckoned pose.

Pure functions mirroring aim_controller.py's shape: a frozen-dataclass state threaded
through ``step``. The host has no pose feedback — the wire is relative deltas only — so
the state carries pan/tilt *estimates* that accumulate every shipped delta, clamped with
the same limits the Pi applies (turret/turret_pi/servo.py — deliberately no shared module).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..config import SentryConfig


@dataclass(frozen=True)
class SentryState:
    """Dead-reckoned pose + sweep bookkeeping. Estimates start at the Pi's startup
    recenter pose (servo.py CENTER: pan 90.0, tilt (20 + 115) / 2 = 67.5)."""

    pan_estimate_deg: float = 90.0
    tilt_estimate_deg: float = 67.5
    direction: float = -1.0  # -1 = sweeping left, +1 = right; first sweep is left
    unlocked_for_s: float = 0.0  # time since the last locked frame


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def step(
    state: SentryState, dt: float, config: SentryConfig
) -> tuple[float, float, SentryState]:
    """One unlocked frame. Returns ``(pan_delta, tilt_delta, new_state)``.

    Silent (zero deltas) until the grace period is exceeded; then emits a constant-speed
    sweep nudge (per-step magnitude capped at ``max_delta_deg`` — stall protection) and a
    tilt-relocation nudge toward ``tilt_default_deg`` that never overshoots. Estimates
    advance by exactly what is emitted; pan flips direction at the clamp bounds.
    """
    unlocked_for_s = state.unlocked_for_s + dt
    if dt <= 0.0 or unlocked_for_s <= config.grace_s:
        return 0.0, 0.0, replace(state, unlocked_for_s=unlocked_for_s)

    step_mag = min(config.speed_deg_s * dt, config.max_delta_deg)

    new_pan = _clamp(
        state.pan_estimate_deg + state.direction * step_mag,
        config.pan_min_deg,
        config.pan_max_deg,
    )
    pan_delta = new_pan - state.pan_estimate_deg
    hit_bound = new_pan in (config.pan_min_deg, config.pan_max_deg)
    direction = -state.direction if hit_bound else state.direction

    remaining = config.tilt_default_deg - state.tilt_estimate_deg
    tilt_delta = _clamp(remaining, -step_mag, step_mag)

    return pan_delta, tilt_delta, SentryState(
        pan_estimate_deg=new_pan,
        tilt_estimate_deg=state.tilt_estimate_deg + tilt_delta,
        direction=direction,
        unlocked_for_s=unlocked_for_s,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_sentry.py -v`
Expected: 3 passed.

- [ ] **Step 6: Fix the spec's CENTER line** — in `docs/superpowers/specs/2026-07-22-sentry-mode-design.md`, replace:

```
- Both start at **90.0°** — the Pi's `ServoDriver` recenters to `CENTER` (90/90) on startup.
```

with:

```
- Estimates start at the Pi's startup recenter pose — `ServoDriver` recenters to
  `CENTER` (pan 90.0°, tilt 67.5°, the midpoint of the 20–115° tilt clamps) on startup.
```

- [ ] **Step 7: Run the full suite (regression check)**

Run: `python -m pytest tests/ -v`
Expected: all pass (nothing existing touched except config additions).

- [ ] **Step 8: Commit**

```bash
git add object_tracker/config.py object_tracker/turret_sink/sentry.py tests/test_sentry.py docs/superpowers/specs/2026-07-22-sentry-mode-design.md
git commit -m "feat: sentry config + grace-period state machine skeleton"
```

---

### Task 2: Pan sweep — direction, bounds, stall clamp

**Files:**
- Modify: `tests/test_sentry.py` (append tests)
- Modify: `object_tracker/turret_sink/sentry.py` (only if a test exposes a bug — `step` was written complete in Task 1)

**Interfaces:**
- Consumes: `SentryState`, `step`, `SentryConfig` exactly as produced by Task 1.
- Produces: verified sweep behaviour Task 5's sink tests rely on; helper `_past_grace` used by Task 4's tests.

- [ ] **Step 1: Append the tests** to `tests/test_sentry.py`:

```python
def _past_grace(pan: float = 90.0, direction: float = -1.0) -> SentryState:
    """A state already past the grace period, so step() sweeps immediately."""
    return SentryState(
        pan_estimate_deg=pan,
        tilt_estimate_deg=CFG.tilt_default_deg,
        direction=direction,
        unlocked_for_s=CFG.grace_s + 1.0,
    )


def test_first_sweep_direction_is_left():
    pan, _, _ = step(_past_grace(), dt=0.1, config=CFG)

    assert pan < 0.0  # decreasing pan = left
    assert pan == -CFG.speed_deg_s * 0.1  # constant speed: 15 deg/s * 0.1 s


def test_direction_flips_at_the_low_bound_and_estimate_stays_in_range():
    state = _past_grace(pan=0.5, direction=-1.0)

    pan, _, state = step(state, dt=0.1, config=CFG)  # wants -1.5, only 0.5 available

    assert pan == -0.5  # truncated at the bound
    assert state.pan_estimate_deg == CFG.pan_min_deg
    assert state.direction == 1.0  # flipped

    pan, _, state = step(state, dt=0.1, config=CFG)  # now sweeps right
    assert pan > 0.0


def test_direction_flips_at_the_high_bound():
    state = _past_grace(pan=179.9, direction=1.0)

    pan, _, state = step(state, dt=0.1, config=CFG)

    assert state.pan_estimate_deg == CFG.pan_max_deg
    assert state.direction == -1.0


def test_large_dt_output_is_clamped_to_max_delta_on_both_axes():
    state = SentryState(  # tilt far from default so both axes want a big step
        pan_estimate_deg=90.0,
        tilt_estimate_deg=CFG.tilt_min_deg,
        direction=-1.0,
        unlocked_for_s=CFG.grace_s + 1.0,
    )

    pan, tilt, _ = step(state, dt=10.0, config=CFG)  # 15 deg/s * 10 s = 150, clamp 5

    assert abs(pan) == CFG.max_delta_deg
    assert abs(tilt) <= CFG.max_delta_deg
```

- [ ] **Step 2: Run the tests**

Run: `python -m pytest tests/test_sentry.py -v`
Expected: all pass if Task 1's `step` is correct; if any fail, fix `sentry.py` (never the tests) until green.

- [ ] **Step 3: Commit**

```bash
git add tests/test_sentry.py object_tracker/turret_sink/sentry.py
git commit -m "test: sentry pan sweep — first-left, bound flips, stall clamp"
```

---

### Task 3: Tilt relocation — monotone, no overshoot, parks at zero

**Files:**
- Modify: `tests/test_sentry.py` (append tests)
- Modify: `object_tracker/turret_sink/sentry.py` (only on test failure)

**Interfaces:**
- Consumes: Task 1's `SentryState`, `step`, `SentryConfig`.
- Produces: verified tilt behaviour Task 5's sink tests rely on.

- [ ] **Step 1: Append the tests** to `tests/test_sentry.py`:

```python
def test_tilt_walks_to_default_without_overshoot_final_step_is_exact_remainder():
    state = SentryState(  # 2.5 deg below default; per-step at dt=0.1 is 1.5 deg
        pan_estimate_deg=90.0,
        tilt_estimate_deg=CFG.tilt_default_deg - 2.5,
        direction=-1.0,
        unlocked_for_s=CFG.grace_s + 1.0,
    )

    _, tilt1, state = step(state, dt=0.1, config=CFG)
    _, tilt2, state = step(state, dt=0.1, config=CFG)

    assert tilt1 == 1.5  # full-speed step toward the default
    assert tilt2 == 1.0  # exact remainder, no overshoot
    assert state.tilt_estimate_deg == CFG.tilt_default_deg


def test_tilt_already_at_default_emits_zero_every_frame():
    state = SentryState(
        pan_estimate_deg=90.0,
        tilt_estimate_deg=CFG.tilt_default_deg,
        direction=-1.0,
        unlocked_for_s=CFG.grace_s + 1.0,
    )

    for _ in range(5):
        _, tilt, state = step(state, dt=0.1, config=CFG)
        assert tilt == 0.0
    assert state.tilt_estimate_deg == CFG.tilt_default_deg


def test_tilt_approaches_from_above_the_default_too():
    state = SentryState(
        pan_estimate_deg=90.0,
        tilt_estimate_deg=CFG.tilt_default_deg + 0.7,
        direction=-1.0,
        unlocked_for_s=CFG.grace_s + 1.0,
    )

    _, tilt, state = step(state, dt=0.1, config=CFG)

    assert tilt == -0.7  # exact remainder downward
    assert state.tilt_estimate_deg == CFG.tilt_default_deg
```

- [ ] **Step 2: Run the tests**

Run: `python -m pytest tests/test_sentry.py -v`
Expected: all pass (fix `sentry.py` if not — never the tests).

- [ ] **Step 3: Commit**

```bash
git add tests/test_sentry.py object_tracker/turret_sink/sentry.py
git commit -m "test: sentry tilt relocation — monotone to default, no overshoot"
```

---

### Task 4: `observe_aim` — locked frames feed the estimates

**Files:**
- Modify: `object_tracker/turret_sink/sentry.py` (add `observe_aim`)
- Modify: `tests/test_sentry.py` (append tests; extend the import line)

**Interfaces:**
- Consumes: Task 1's `SentryState`, `SentryConfig`, `_clamp`; Task 2's `_past_grace` helper.
- Produces: `observe_aim(state: SentryState, pan_delta: float, tilt_delta: float, config: SentryConfig) -> SentryState` — Task 5's sink calls this on every locked frame with the shipped `AimCommand`'s deltas.

- [ ] **Step 1: Append the failing tests** to `tests/test_sentry.py`. Change the import at the top of the file to:

```python
from object_tracker.turret_sink.sentry import SentryState, observe_aim, step
```

Then append:

```python
def test_observe_aim_accumulates_both_axes_and_clamps():
    state = SentryState(pan_estimate_deg=179.0, tilt_estimate_deg=114.0)

    state = observe_aim(state, pan_delta=5.0, tilt_delta=5.0, config=CFG)

    assert state.pan_estimate_deg == CFG.pan_max_deg  # 184 clamped to 180
    assert state.tilt_estimate_deg == CFG.tilt_max_deg  # 119 clamped to 115


def test_observe_aim_resets_grace_timer_and_sweep_direction():
    state = SentryState(direction=1.0, unlocked_for_s=99.0)

    state = observe_aim(state, pan_delta=0.0, tilt_delta=0.0, config=CFG)

    assert state.unlocked_for_s == 0.0
    assert state.direction == -1.0  # next sweep starts left again


def test_relock_then_unlock_sweeps_left_again():
    from dataclasses import replace

    state = _past_grace(direction=1.0)  # was sweeping right
    state = observe_aim(state, pan_delta=-2.0, tilt_delta=1.0, config=CFG)  # locked frame
    state = replace(state, unlocked_for_s=CFG.grace_s + 1.0)  # unlocked again, past grace

    pan, _, _ = step(state, dt=0.1, config=CFG)

    assert pan < 0.0  # left again
```

- [ ] **Step 2: Run to verify the new tests fail**

Run: `python -m pytest tests/test_sentry.py -v`
Expected: collection ERROR with `ImportError: cannot import name 'observe_aim'`.

- [ ] **Step 3: Implement `observe_aim`** — append to `object_tracker/turret_sink/sentry.py`:

```python
def observe_aim(
    state: SentryState, pan_delta: float, tilt_delta: float, config: SentryConfig
) -> SentryState:
    """A locked frame shipped an Aim Command: fold its deltas into the estimates
    (clamped like the Pi clamps), reset the grace timer, and re-arm the first
    sweep direction (left)."""
    return SentryState(
        pan_estimate_deg=_clamp(
            state.pan_estimate_deg + pan_delta, config.pan_min_deg, config.pan_max_deg
        ),
        tilt_estimate_deg=_clamp(
            state.tilt_estimate_deg + tilt_delta, config.tilt_min_deg, config.tilt_max_deg
        ),
        direction=-1.0,
        unlocked_for_s=0.0,
    )
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_sentry.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_sentry.py object_tracker/turret_sink/sentry.py
git commit -m "feat: sentry observe_aim — locked frames feed the dead-reckoned pose"
```

---

### Task 5: `ActuatorSink` integration — the unlocked branch

**Files:**
- Modify: `object_tracker/turret_sink/actuator_sink.py`
- Modify: `tests/test_actuator_sink.py` (append tests + a fake clock)

**Interfaces:**
- Consumes: `sentry.SentryState`, `sentry.step`, `sentry.observe_aim`, `config.SentryConfig`, existing `AimCommand`.
- Produces: `ActuatorSink.__init__(transport, gains, frame_wh, sentry_config: SentryConfig | None = None, clock: Callable[[], float] = time.monotonic)`. The existing call site `object_tracker/cli.py:108` needs **no change** (new params default). Behaviour: locked → aim (unchanged) + `observe_aim`; unlocked → `sentry.step`, ship an `AimCommand` when either delta is nonzero.

- [ ] **Step 1: Append the failing tests** to `tests/test_actuator_sink.py`:

```python
class FakeClock:
    """Deterministic monotonic clock: advance() controls each frame's dt exactly."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, dt: float) -> None:
        self.now += dt


def _sentry_sink(transport):
    from object_tracker.config import SentryConfig

    clock = FakeClock()
    sink = ActuatorSink(
        transport, _gains(), FRAME_WH, sentry_config=SentryConfig(), clock=clock
    )
    return sink, clock


def _run_unlocked_frames(sink, clock, n, dt):
    for _ in range(n):
        clock.advance(dt)
        sink.show(_blank_frame(), sv.Detections.empty())


def test_unlocked_frames_within_grace_send_nothing():
    transport = FakeTransport()
    sink, clock = _sentry_sink(transport)

    # first frame's dt collapses to 0 (no prior timestamp) -> 1.0 s unlocked < 2.0 s grace
    _run_unlocked_frames(sink, clock, n=3, dt=0.5)

    assert transport.sent == []


def test_unlocked_past_grace_ships_sweeps_and_tilt_walks_to_default_then_zero():
    transport = FakeTransport()
    sink, clock = _sentry_sink(transport)

    # first frame's dt collapses to 0; 39 x 0.1 s = 3.9 s unlocked -> 19 sweep frames,
    # enough for the 22.5-deg tilt walk (15 frames at 1.5 deg/frame) plus settled frames
    _run_unlocked_frames(sink, clock, n=40, dt=0.1)

    assert transport.sent, "expected sweep commands after the grace period"
    assert all(c.pan_delta < 0.0 for c in transport.sent)  # first sweep is left
    # tilt: estimate starts at 67.5, default is 90 -> deltas walk up, then settle at 0
    assert transport.sent[0].tilt_delta > 0.0
    assert transport.sent[-1].tilt_delta == 0.0


def test_target_appearing_mid_sweep_ships_an_aim_command_on_the_next_frame():
    transport = FakeTransport()
    sink, clock = _sentry_sink(transport)
    _run_unlocked_frames(sink, clock, n=25, dt=0.1)  # sweeping
    sweeps = len(transport.sent)

    clock.advance(0.1)
    sink.show(_blank_frame(), _tracked([5], [[60, 20, 80, 30]]))  # target appears

    assert len(transport.sent) == sweeps + 1
    assert transport.sent[-1].pan_delta > 0.0  # aim toward the target (right of centre)


def test_aim_deltas_shipped_while_locked_shift_where_the_sweep_resumes():
    from object_tracker.config import SentryConfig

    transport = FakeTransport()
    sink, clock = _sentry_sink(transport)

    clock.advance(0.1)
    sink.show(_blank_frame(), _tracked([5], [[60, 20, 80, 30]]))  # locks id 5
    aim = transport.sent[-1]
    assert aim.pan_delta == 2.0  # kp=0.1 * error 20 px — the delta observe_aim folds in

    _run_unlocked_frames(sink, clock, n=25, dt=0.1)  # grace passes, sweep begins

    # Dead reckoning: the pan estimate was 90 + 2 = 92 when the sweep began (left);
    # the summed sweep deltas can never take the estimate below the pan clamp.
    swept = sum(c.pan_delta for c in transport.sent[1:])
    assert 92.0 + swept >= SentryConfig().pan_min_deg
```

- [ ] **Step 2: Run to verify the new tests fail**

Run: `python -m pytest tests/test_actuator_sink.py -v`
Expected: the four new tests FAIL with `TypeError: ActuatorSink.__init__() got an unexpected keyword argument 'sentry_config'`. The six pre-existing tests must still pass.

- [ ] **Step 3: Implement the sink changes** — `object_tracker/turret_sink/actuator_sink.py` becomes:

```python
"""Actuator Sink (ADR-0013): the FrameSink that aims the turret instead of drawing.

Glue only — pulls the frame's Track centres, threads Target Selector + Aim Controller, and
ships the resulting Aim Command down the configured AimTransport. Mirrors the existing
sinks.py shape: a thin, stateful wrapper around pure functions, the same
pure-step-wrapped-in-a-stateful-manager pattern zoom.py's ZoomSlots already uses.

Sentry mode (2026-07-22 design): unlocked frames thread the sentry state machine; after
the grace period the sink ships sweep nudges through the same transport/seq path. All
decisions live in sentry.py — this class stays glue.
"""

from __future__ import annotations

import time
from typing import Callable

import numpy as np
import supervision as sv

from ..config import AimGains, SentryConfig
from ..tracking import _present_centers
from .aim_controller import AimCommand, AimControllerState, step
from .sentry import SentryState, observe_aim
from .sentry import step as sentry_step
from .target_selector import select_target
from .transport import AimTransport


class ActuatorSink:
    """A FrameSink that never draws; always returns True (never asks the loop to stop)."""

    def __init__(
        self,
        transport: AimTransport,
        gains: AimGains,
        frame_wh: tuple[int, int],
        sentry_config: SentryConfig | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transport = transport
        self._gains = gains
        self._center = (frame_wh[0] / 2.0, frame_wh[1] / 2.0)
        self._locked_id: int | None = None
        self._state = AimControllerState()
        self._last_ts: float | None = None
        self._sentry_config = sentry_config if sentry_config is not None else SentryConfig()
        self._sentry = SentryState()
        self._clock = clock

    def show(self, frame: np.ndarray, tracks: sv.Detections | None = None) -> bool:
        present = _present_centers(tracks) if tracks is not None else {}
        self._locked_id = select_target(frozenset(present.keys()), self._locked_id)
        now = self._clock()
        dt = 0.0 if self._last_ts is None else max(0.0, now - self._last_ts)
        self._last_ts = now
        if self._locked_id is not None:
            target = present[self._locked_id]
            error = (target[0] - self._center[0], target[1] - self._center[1])
            command, self._state = step(error, self._gains, self._state, dt)
            self._transport.send(command)
            self._sentry = observe_aim(
                self._sentry, command.pan_delta, command.tilt_delta, self._sentry_config
            )
        else:
            pan_delta, tilt_delta, self._sentry = sentry_step(
                self._sentry, dt, self._sentry_config
            )
            if pan_delta != 0.0 or tilt_delta != 0.0:
                self._transport.send(AimCommand(pan_delta=pan_delta, tilt_delta=tilt_delta))
        return True

    def close(self) -> None:
        self._transport.close()
```

- [ ] **Step 4: Run the sink tests**

Run: `python -m pytest tests/test_actuator_sink.py -v`
Expected: all pass (six old + four new).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -v`
Expected: all pass. `tests/test_cli.py` matters most — `cli.py` constructs ActuatorSink positionally and is unchanged.

- [ ] **Step 6: Commit**

```bash
git add object_tracker/turret_sink/actuator_sink.py tests/test_actuator_sink.py
git commit -m "feat: sentry mode — ActuatorSink sweeps when no target is locked"
```

---

### Task 6: Lint, format, final verification

**Files:**
- Possibly touched by formatters: everything from Tasks 1–5.

- [ ] **Step 1: Format and lint**

```bash
black object_tracker/turret_sink/sentry.py object_tracker/turret_sink/actuator_sink.py object_tracker/config.py tests/test_sentry.py tests/test_actuator_sink.py
```

```bash
ruff check object_tracker tests --fix
```

Expected: no remaining ruff errors on the touched files.

- [ ] **Step 2: Full suite one last time**

Run: `python -m pytest tests/ -v`
Expected: all pass. Confirm the Pi side is untouched: `git status turret/` shows no changes.

- [ ] **Step 3: Commit any formatter fallout**

```bash
git add -u
git commit -m "chore: format sentry-mode files"
```

(Skip the commit if the formatters changed nothing.)
