# Sentry Mode — Design

**Date:** 2026-07-22
**Status:** Approved (brainstorming session 2026-07-22)
**Amended:** 2026-07-22 — tilt now relocates to a default patrol angle during the sweep
(was: held at its last angle); the default lives in `sentry.py`.
**Extends:** ADR-0013 (pan-tilt turret as Actuator Sink)

## Problem

When the Actuator Sink has no Track to follow, the turret holds position forever
(ADR-0013 v1: "no ids present → hold"). A turret that never looks around cannot
re-acquire a target that left the frame, and cannot find a first target at all unless
one happens to walk into view. We want a **sentry mode**: when nothing is detected for
a while, the turret sweeps its pan axis across the full 0–180° range until a target
appears, then snaps back to normal tracking.

## Decisions (from brainstorming)

| Question | Decision |
|---|---|
| When does the sweep start? | After a short grace period (`SENTRY_GRACE_S = 2.0` s) with no locked Track — brief occlusions must not trigger a sweep. |
| Sweep pattern | **Continuous triangle wave** at constant speed: sweep to one limit, reverse, repeat. Chosen over step-and-stare because the moment a detection appears, the sink must hand over to the tracking loop on the very next frame — a slow continuous sweep guarantees the new target is still in frame at handover. |
| Sweep speed | `SENTRY_SPEED_DEG_S = 15.0` °/s (full 180° pass in 12 s). Slowest option considered — minimises motion blur (small/distant objects are the primary use case) and keeps the find-to-track overshoot at ~0.8–3° given the 50–200 ms loop latency. |
| First direction | **Left** (decreasing pan), starting from the current pan position, per the original request. |
| Tilt during sweep | **Relocated to a default patrol angle.** Once the grace period elapses, tilt is driven (rate-limited, via the same relative-delta wire) to `SENTRY_TILT_DEFAULT_DEG` — declared in `sentry.py` next to the state machine — and held there for the rest of the sweep. Supersedes the original "hold last tilt" decision: a fixed patrol tilt gives a predictable guard posture regardless of where the last target vanished. |
| How is it enabled? | Automatically with `--turret`. No new flag: a turret that guards on its own is the point of the feature. |
| Where does the sweep logic live? | **Host-side** (Approach A below). |

## Approaches considered

- **A. Host-side sweep with dead-reckoned pose (chosen).** The host estimates the
  absolute pan angle by accumulating every `pan_delta` it ships, and emits sweep
  nudges through the existing relative-delta wire. No Pi changes, no wire changes,
  brain stays on the Mac (ADR-0013), fully unit-testable, works against
  `scripts/fake_turret_listener.py`.
- **B. Pi-side sweep on quiet wire.** Rejected: violates "the Pi is the actuator
  only", splits no-target logic across two deployables, and cannot distinguish
  "no target" from "host crashed".
- **C. Extend the wire protocol (absolute pose commands / pose feedback).**
  Rejected: touches both deployables and adds message types for a feature one pure
  host-side unit can deliver (YAGNI).

## The dead-reckoning problem — and why it self-corrects

The wire carries only relative nudges (`{"pan_delta", "tilt_delta", "seq"}`); the Pi
never reports its pose. The host therefore keeps a **pan estimate and a tilt estimate**:

- Both start at **90.0°** — the Pi's `ServoDriver` recenters to `CENTER` (90/90) on startup.
- Every delta the sink ships (tracking **and** sentry alike) is accumulated
  into its estimate, then clamped to 0–180 with the same limits the Pi applies
  (`turret_pi/servo.py`: `PAN_MIN_DEG = 0.0`, `PAN_MAX_DEG = 180.0`, and the tilt
  equivalents).
- **Pan self-correction at the limits:** if UDP loss makes the estimate drift from the
  true pose, each sweep runs both the estimate and the real servo into the same hard
  clamp (0 or 180). Saturation equalises them, so drift is bounded and is re-zeroed
  every half sweep. Mid-sweep drift is accepted and documented; it cannot accumulate.
- **Tilt has no such re-zeroing:** the relocation drives tilt to
  `SENTRY_TILT_DEFAULT_DEG` (mid-range, not a mechanical limit), so tilt never
  saturates and lost datagrams leave a residual offset between the estimate and the
  real servo. The drift is bounded by the clamps, cannot grow while tilt sits at the
  default (zero deltas ship), and resets whenever the Pi restarts and recenters.
  Accepted for v1 — same spirit as the sender-restart case below.

The host-side limit constants **mirror** the Pi's but are declared independently —
the two sides deliberately share no module (ADR-0013). A comment on each side points
at the other.

## Components

### New: `object_tracker/turret_sink/sentry.py` — pure state machine

Mirrors `aim_controller.py`'s shape: a frozen-dataclass state threaded through a pure
`step` function.

```python
SENTRY_TILT_DEFAULT_DEG = 90.0       # patrol tilt the sweep relocates to
                                     # (deliberately configured HERE, not config.py)

@dataclass(frozen=True)
class SentryState:
    pan_estimate_deg: float = 90.0   # dead-reckoned absolute pan
    tilt_estimate_deg: float = 90.0  # dead-reckoned absolute tilt
    direction: float = -1.0          # -1 = sweeping left, +1 = right
    unlocked_for_s: float = 0.0      # time since the last locked frame

def observe_aim(state: SentryState, pan_delta: float, tilt_delta: float) -> SentryState:
    """A locked frame shipped deltas: fold both into the estimates (clamped),
    reset the grace timer and the sweep direction (next sweep starts left)."""

def step(state: SentryState, dt: float, config: SentryConfig) -> tuple[float, float, SentryState]:
    """An unlocked frame: advance the grace timer; once it exceeds the grace
    period, emit a sweep `pan_delta` (direction * speed * dt, clamped to
    max_delta_deg) and a relocation `tilt_delta` stepping the tilt estimate
    toward SENTRY_TILT_DEFAULT_DEG (same speed and per-step clamp), advance
    both estimates, and flip pan direction at 0/180."""
```

Exact signatures may shrink during TDD; the invariants are what matter:

1. No sweep output until `unlocked_for_s > grace period`.
2. First sweep direction after any lock (or at startup) is **left**.
3. The estimates reflect **every** shipped delta, tracking or sentry, on both axes.
4. Estimates are always clamped to [0, 180]; pan hitting a bound flips `direction`.
5. A single step's output never exceeds `max_delta_deg` on either axis (stall
   protection: a huge `dt` from a pipeline hiccup must not produce a violent jump).
6. `dt = 0` (first frame) emits no motion.
7. Sweep frames drive `tilt_estimate_deg` toward `SENTRY_TILT_DEFAULT_DEG`
   monotonically, never overshooting it; once the estimate sits at the default,
   `tilt_delta = 0` for the rest of the sweep.

### Changed: `object_tracker/turret_sink/actuator_sink.py`

`ActuatorSink.show` grows a second branch. Today: locked → aim; unlocked → nothing.
After:

- **Locked:** unchanged aim path; additionally
  `observe_aim(state, command.pan_delta, command.tilt_delta)` so the estimates
  track reality.
- **Unlocked:** `step(state, dt, config)`; when it yields a nonzero delta on either
  axis, ship `AimCommand(pan_delta=pan, tilt_delta=tilt)` through the same
  transport/seq path.

The sink stays glue-only: all decisions live in `sentry.py`.

### Changed: `object_tracker/config.py`

```python
SENTRY_GRACE_S = 2.0          # unlocked time before the sweep starts
SENTRY_SPEED_DEG_S = 15.0     # continuous sweep speed (pan sweep AND tilt relocation)
SENTRY_PAN_MIN_DEG = 0.0      # mirrors turret_pi/servo.py PAN_MIN_DEG (no shared module)
SENTRY_PAN_MAX_DEG = 180.0    # mirrors turret_pi/servo.py PAN_MAX_DEG
```

Plus a small frozen `SentryConfig` dataclass if it keeps `step`'s signature clean.
Constants, not CLI flags (same reasoning as ADR-0011's Appearance: tuning values,
not run-shape choices).

Exception: `SENTRY_TILT_DEFAULT_DEG` lives in `sentry.py`, not here (amendment
decision) — it is the state machine's own target pose, and keeping it beside the
relocation logic that consumes it makes `sentry.py` the single file to edit when
retuning the patrol posture.

### Unchanged

`turret_pi/*` (all of it), `wire.py` (both sides), `transport.py`,
`target_selector.py`, `aim_controller.py`, `pipeline.py`, CLI surface.

## Data flow

```
tracks --> ActuatorSink.show
             ├─ locked   --> select_target -> aim step -> send ─┬─> observe_aim(state)
             └─ unlocked --> sentry.step(state, dt) ─ deltas? ──┴─> send AimCommand(pan, tilt→default)
                                                     (grace not yet elapsed -> send nothing)
```

The Pi cannot tell sentry nudges from aim nudges — by design. The Command Listener's
superseding contract and the Servo Driver's clamp both apply unchanged.

## Error handling

- **First frame / `dt = 0`:** no motion (invariant 6).
- **Pipeline stall (large `dt`):** per-step output clamped to `max_delta_deg`
  (invariant 5); the estimate only advances by what was actually shipped.
- **UDP loss:** pan estimate drifts mid-sweep, bounded, re-zeroed at each limit;
  tilt estimate drifts without a re-zeroing point but cannot grow once tilt parks
  at the default (see dead-reckoning section). Accepted.
- **Sender restart:** host restarts → estimates reset to 90/90 but the Pi may not be
  there. Worst case the first sweep is asymmetric and the patrol tilt is offset by
  the lost amount; the first pan limit hit re-syncs pan, and a Pi restart re-syncs
  both. Accepted for v1 (same spirit as ADR-0013's "freshest command wins").

## Testing (TDD, pytest, AAA)

New `tests/test_sentry.py` covering each invariant above as its own test
(pure functions — no hardware, no sockets, fake time via explicit `dt`):

- grace period: below → no output; crossing → output begins
- first direction is left; re-lock then unlock again → left again
- direction flips at 0 and at 180; estimates never leave [0, 180]
- `observe_aim` accumulates tracking deltas (both axes) and clamps
- large `dt` → output clamped to `max_delta_deg` on both axes
- `dt = 0` → zero output
- tilt relocation: sweep steps drive `tilt_estimate_deg` toward
  `SENTRY_TILT_DEFAULT_DEG` without overshoot (final step is the exact remainder)
- tilt already at default when the sweep starts → `tilt_delta = 0` on every frame
- tilt parked at default mid-sweep → subsequent frames emit `tilt_delta = 0`

Extended `tests/test_actuator_sink.py`:

- unlocked frames within grace → transport receives nothing (current behaviour holds)
- unlocked past grace → transport receives sweep commands whose tilt deltas walk
  the pose to the default, then settle at `tilt_delta == 0`
- target appears mid-sweep → very next frame ships an aim command, not a sweep one
- estimate consistency: aim deltas shipped while locked shift where the sweep
  resumes (pan) and how far the tilt relocation has to travel

`turret_pi` test suite untouched.

## Out of scope (YAGNI, recorded so they stay out)

- Tilt sweep / 2-axis patrol patterns
- Pi-side autonomy or pose feedback on the wire
- Configurable sweep sectors (e.g. only 45–135°)
- A `--sentry` CLI flag or per-run speed flags — constants first; promote to flags
  only when real tuning pressure appears
