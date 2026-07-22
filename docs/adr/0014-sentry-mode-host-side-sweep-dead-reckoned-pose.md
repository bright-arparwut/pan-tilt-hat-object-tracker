# Sentry mode: host-side no-target sweep with a dead-reckoned pose

ADR-0013 left the [Actuator Sink] with an honest but passive failure mode: when the locked
[Track] disappears and none re-latches, the turret holds position forever. A turret that never
looks around cannot re-acquire a target that left the frame, and cannot find a first target at
all. **Sentry mode** replaces the hold: after a short grace period with no locked [Track], the
sink sweeps the pan axis across its full range until a target appears, then hands back to
tracking on the very next frame. The full design (with sweep-speed math and test invariants)
lives in `docs/superpowers/specs/2026-07-22-sentry-mode-design.md`; this ADR records the
load-bearing choices.

## Host-side sweep through the existing wire (the load-bearing decision)

The sweep is a **pure host-side state machine** (`object_tracker/turret_sink/sentry.py`,
mirroring `aim_controller.py`'s frozen-dataclass-through-pure-`step` shape) that emits ordinary
[Aim Command]s through the existing relative-delta wire. No Pi changes, no wire changes: **the
Pi cannot tell a sentry nudge from an aim nudge, by design.** The [Command Listener]'s
superseding contract and the [Servo Driver]'s clamps apply unchanged.

The sink stays glue: locked frames take the unchanged aim path (now also feeding the sweep's
pose bookkeeping), unlocked frames step the sentry machine. All decisions live in `sentry.py`.

## Dead reckoning, and where it self-corrects

The wire carries only relative nudges and the Pi never reports its pose, so the host keeps a
**[Pose Estimate]**: pan and tilt estimates that start at the Pi's startup recenter pose
(`ServoDriver` `CENTER`: pan 90.0°, tilt 67.5° — the midpoint of each axis's clamps) and
accumulate **every** shipped delta, tracking and sentry alike, clamped with host-side mirrors
of `turret_pi/servo.py`'s limits (pan 0–180, tilt 20–115). The two sides deliberately share no
module (ADR-0013); a comment on each side points at the other.

- **Pan self-corrects at the limits:** every sweep runs both the estimate and the real servo
  into the same hard clamp, so UDP-loss drift is bounded and re-zeroed each half sweep.
- **Tilt does not:** the sweep relocates tilt to a mid-range patrol default
  (`SENTRY_TILT_DEFAULT_DEG`), which never saturates, so lost datagrams leave a bounded
  residual offset that only a Pi restart clears. Accepted for v1 — same spirit as ADR-0013's
  "freshest command wins".

## Sweep shape

- **Grace period first** (`SENTRY_GRACE_S = 2.0` s of no locked [Track]) so brief occlusions
  never trigger a sweep; the [Tracker]'s own lost-track buffer keeps the id (and the lock)
  alive through short gaps.
- **Continuous triangle wave** at `SENTRY_SPEED_DEG_S = 15.0` °/s, chosen over step-and-stare
  so a target found mid-sweep is still in frame at handover; slow enough to limit motion blur
  on small/distant objects. First direction is **left**, re-armed on every re-lock.
- **Tilt relocates** (rate-limited, same wire) to the patrol default and parks there — a
  predictable guard posture regardless of where the last target vanished. This superseded the
  original "hold last tilt" during design.
- **Stall protection:** a single step's output never exceeds the turret's per-step slew clamp,
  so a pipeline hiccup's huge `dt` cannot produce a violent jump; `dt = 0` emits nothing.
- **Enabled automatically with `--turret`** — a turret that guards on its own is the point.
  Tuning lives as constants in `config.py` (`SentryConfig`), not CLI flags (ADR-0011's
  reasoning: tuning values, not run-shape choices).

## Considered options

- **Pi-side sweep on a quiet wire** — rejected: violates "the Pi is the actuator only"
  (ADR-0013), splits no-target logic across two deployables, and cannot distinguish "no
  target" from "host crashed".
- **Extending the wire protocol** (absolute pose commands / pose feedback) — rejected: touches
  both deployables and adds message types for a feature one pure host-side unit delivers
  (YAGNI). Dead reckoning with limit re-zeroing is good enough for a sweep.
- **Step-and-stare sweep** — rejected: the pause-move-pause rhythm risks the found target
  leaving frame during the handover latency window; a slow continuous sweep does not.
- **A `--sentry` flag or per-run speed flags** — deferred: constants first; promote to flags
  only when real tuning pressure appears.

## Consequences

- **ADR-0013's "holds position" failure mode is superseded.** Unlocked frames inside the grace
  period still send nothing (the old behaviour, byte-for-byte); past it, the turret guards.
- **The host now models turret state.** The [Pose Estimate] is the first host-side belief
  about the physical world; it is deliberately a *belief* — mid-sweep drift is accepted and
  documented, and a host restart resets the estimates while the Pi may be elsewhere (first
  pan-limit hit re-syncs pan; a Pi restart re-syncs both).
- **New vocabulary** — [Sentry Mode], [Pose Estimate] — added to `CONTEXT.md`.
- **Testability preserved:** `sentry.py` is pure (time arrives as explicit `dt`; the sink's
  clock is injectable), so every invariant is unit-tested without hardware or sockets, and the
  whole behaviour works against `scripts/fake_turret_listener.py`.
- **Out of scope, recorded so they stay out:** tilt sweep / 2-axis patrol patterns, Pi-side
  autonomy or pose feedback, configurable sweep sectors.
