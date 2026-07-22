# turret-pi

Pi-side actuator for the pan-tilt tracking turret (ADR-0013). Runs on the Raspberry Pi
only, as a package separate from `object_tracker` (different runtime host, disjoint
dependency graph — see `docs/adr/0013-pan-tilt-turret-as-actuator-sink.md`).

Ships the full Pi-side actuator: `servo.ServoAngles`/`clamp_angles` plus the real I²C
`ServoDriver` (PCA9685), `wire.decode`, `listener.run_listener` — the UDP command loop that
decodes Aim Commands, drops the malformed and the stale (freshest-command-wins by `seq`), and
nudges a `Servo` — the MJPEG `streamer`, the `teleop` calibration harness, and `main.py` (the
`uv run turret` entrypoint, which injects the driver into `run_listener`). The pure units depend
only on a `Servo` Protocol (`apply_delta`), so they run and are unit-tested with no HAT attached;
the I²C and camera paths are verified on the Pi (see `DEPLOY.md`).

## Setup

```bash
uv sync
uv run pytest
```
