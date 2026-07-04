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
