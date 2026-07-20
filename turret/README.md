# turret-pi

Pi-side actuator for the pan-tilt tracking turret (ADR-0013). Runs on the Raspberry Pi
only, as a package separate from `object_tracker` (different runtime host, disjoint
dependency graph — see `docs/adr/0013-pan-tilt-turret-as-actuator-sink.md`).

Currently ships the hardware-free units: `servo.ServoAngles`/`clamp_angles`, `wire.decode`,
and `listener.run_listener` — the UDP command loop that decodes Aim Commands, drops the
malformed and the stale (freshest-command-wins by `seq`), and nudges a `Servo`. The listener
depends only on a `Servo` Protocol (`apply_delta`), so it runs and is tested with no HAT
attached. Still a follow-up once Phase 0 hardware bring-up has picked a concrete HAT SDK: the
real I²C `ServoDriver`, the MJPEG `streamer`, and `main.py` (which injects the driver into
`run_listener`).

## Setup

```bash
uv sync
uv run pytest
```
