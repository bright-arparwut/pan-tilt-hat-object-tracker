# `turret_pi` — the Pi-side actuator (sandbox skeleton)

The Raspberry Pi half of the pan-tilt tracking turret. **Weeks 9–12.**

The Pi is the actuator; the Mac is the brain. This package must never grow a `torch`
dependency — that split is the point (ADR-0013).

| Package | Runs on | Heavy deps |
|---|---|---|
| `learn/object_tracker/` | Mac only | ultralytics, torch, supervision |
| `learn/turret/` → `turret_pi` | **Pi only** | opencv-python, adafruit-circuitpython-servokit |

## Develop on the Mac

```bash
cd learn/turret
uv sync            # NOT --extra hardware; you don't need the Pi SDK to develop
uv run pytest      # every pure unit is testable here
```

Every module imports cleanly on a Mac because the hardware SDKs are imported **lazily** —
`adafruit_servokit` only when no kit is injected, `picamera2` only under `--csi`. Build that
in week 9 and the rest of month 3 stays comfortable.

## Deploy to the Pi

```bash
git push                              # from the Mac
ssh <user>@raspberrypi.local
cd <repo>/learn/turret && git pull && uv sync --extra hardware
uv run turret --port 9000 --stream-port 8000
```

Full bring-up, calibration and troubleshooting: **[DEPLOY.md](DEPLOY.md)**.

Read the servo calibration section **before** you power the HAT. The mechanical limits in
`servo.py` are from the reference build — measure your own.
