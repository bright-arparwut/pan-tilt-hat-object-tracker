# Deploying `turret_pi` to the Raspberry Pi

Bring-up checklist for the Pi side of the pan-tilt tracking turret (ADR-0013). The Pi is the
**actuator**: it runs the servos and streams its camera. The **Mac stays the brain** — all
detection/tracking runs there, unchanged.

## What goes on the Pi (and what doesn't)

Only the **`turret/`** package (`turret_pi`). The Mac-side `object_tracker` (YOLO, torch,
supervision) **never** goes on the Pi — that's the whole point of the one-repo/two-packages split
(ADR-0013). Cloning the whole repo on the Pi is fine; you only ever `uv sync` inside `turret/`, so
the Pi pulls only the small Pi-side dependencies.

| Package | Runs on | Heavy deps |
|---|---|---|
| `object_tracker/` (repo root) | Mac only | ultralytics, torch, supervision |
| `turret/` → `turret_pi` | **Pi only** | opencv-python, adafruit-circuitpython-servokit |

**Dev workflow:** write + unit-test on the Mac (the pure units are Mac-testable), `git push`, then
`git pull` on the Pi and run. The I²C paths can only be *verified* on the Pi.

## Hardware kit

- Raspberry Pi 5
- Waveshare Pan-Tilt HAT (PCA9685 over I²C, at address `0x40`) — drives 2 servos
- 2× servo: **pan = channel 0, tilt = channel 1**
- USB camera, mounted **on the moving platform**
- A proper **5V / 5A** Pi 5 supply (see the brownout note under Troubleshooting)

## Phase 0 — Pi setup (once, headless from the Mac)

1. **Flash Raspberry Pi OS** with Raspberry Pi Imager. In its settings (gear icon) pre-set:
   **WiFi SSID + password** (the *same network as the Mac*), **hostname**, and **enable SSH**. No
   monitor needed.
2. **Boot** the Pi, then SSH in from the Mac:
   ```bash
   ssh <user>@raspberrypi.local        # or ssh <user>@<pi-ip>  (find the IP in your router)
   ```
3. **Enable I²C and verify the HAT is seen:**
   ```bash
   sudo raspi-config nonint do_i2c 0    # enable I2C (or: raspi-config -> Interface -> I2C)
   sudo i2cdetect -y 1                  # PCA9685 shows at 0x40  <- Phase-0 "done" gate
   ```
4. **Install tooling + the code:**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh   # install uv (or your preferred method)
   git clone <this-repo-url>
   cd <repo>/turret
   uv sync                              # installs ONLY the Pi-side deps
   ```

## Hardware assembly

- Seat the Pan-Tilt HAT on the Pi's 40-pin GPIO header.
- Plug the servos into the HAT's **pan (ch 0)** and **tilt (ch 1)** outputs.
- Plug the USB camera into a Pi USB port; route its cable with slack so the platform doesn't fight
  its own wire.
- Power the Pi from a proper **5V/5A** supply, and feed servo power as the HAT specifies.

## Servo calibration (mechanical limits)

The servos' *electrical* range is a full 0–180°, but the assembled bracket's *mechanical* travel is
narrower — driving a servo past where the bracket physically stops **stalls** the motor: it strains,
buzzes, and never settles. Software clamps every commanded angle to the mechanical limits so a stray
command can't do this (ADR-0013), but the limits have to be **measured on the built platform** first.

**Measure with the teleop harness** (on the Pi, HAT powered):
```bash
uv run python -m turret_pi.teleop      # WASD to nudge 5° at a time, q to quit
```
Nudge toward each extreme (`a`/`d` = pan left/right, `w`/`s` = tilt up/down); it prints the pose
after every move. **The moment the platform stops moving or the servo starts to strain/buzz, back
off immediately** — the last angle it reached *freely* is that axis's limit. Holding a servo against
its stop draws a current spike that can brown out the Pi and wear the gears.

**Measured on this build** (frozen in `turret_pi/servo.py`):

| Axis | Min | Max | Notes |
|---|---|---|---|
| Pan | 0° | 180° | full travel — bracket clears both sides |
| Tilt | 20° | 115° | bracket fouls the base below 20°, hits the mount above 115° |

These are the `PAN_MIN_DEG` / `PAN_MAX_DEG` / `TILT_MIN_DEG` / `TILT_MAX_DEG` constants. The
startup/shutdown **safe centre** (`CENTER`) is derived as the mid-range of each axis — **pan 90°,
tilt 67.5°** — so a fresh or recentred turret sits in the middle of its *real* travel, not at a raw
90° that would tilt it hard toward one stop. Re-measure and update these four constants if you
re-bracket or swap servos.

## Running

**On the Pi** — start the actuator (streamer + command listener):
```bash
uv run turret --port 9000 --stream-port 8000
```

**On the Mac** — run the tracker against the Pi's stream and aim the turret:
```bash
uv run track --source http://<pi-ip>:8000/stream.mjpg --track --turret <pi-ip>:9000
```

The connection at runtime is two IP channels: **video up** (MJPEG over HTTP, port 8000) and
**Aim Commands down** (UDP, port 9000). SSH is only for setup/admin.

## Status

All Pi-side units are built and unit-tested Mac-side (no hardware): `wire.decode`,
`ServoAngles`/`clamp_angles`, the **Command Listener** (`run_listener`), the real I²C `ServoDriver`
(PCA9685), the MJPEG Frame **Streamer**, the `teleop` calibration harness, and `main.py` — so the
`turret = "turret_pi.main:main"` entrypoint in `pyproject.toml` runs.

What only the Pi can confirm is the live hardware behaviour: I²C servo motion and USB-camera MJPEG
capture. During bring-up, verify in this order:

1. **Servo axis signs + mechanical limits** — run the teleop harness and calibrate (see *Servo
   calibration*). The sign flip is the classic first bug (ADR-0013): if an axis moves the wrong way,
   flip `PAN_SIGN`/`TILT_SIGN` in `servo.py`.
2. **Camera stream** — start `uv run turret` and open `http://<pi-ip>:8000/stream.mjpg` in a browser.
3. **Closed loop** — run the Mac tracker against the stream (see *Running*).

**Dry-run the command plane without the Pi** — on the Mac, watch the exact Aim Commands the tracker
emits with the no-hardware listener:
```bash
uv run python scripts/fake_turret_listener.py --port 9000      # terminal 1
uv run track --source 0 --track --turret 127.0.0.1:9000        # terminal 2 (Mac webcam)
```

## Troubleshooting

- **Mac can't reach the Pi** — `ping <pi-ip>` from the Mac. If it fails: they're not on the same
  reachable subnet. Common causes: **guest WiFi / client (AP) isolation** blocking device-to-device
  traffic even on the same SSID, or different subnets/VLANs. Use the main network with isolation off.
- **`i2cdetect` shows nothing / no `0x40`** — I²C not enabled (redo step 3), HAT not fully seated,
  or the HAT unpowered.
- **Servos twitch / the Pi randomly reboots** — almost always **power**. Servos draw current spikes
  when moving; an underpowered supply browns out the Pi. Use a proper 5V/5A supply and verify how
  the HAT feeds servo power.
- **Servo moves the wrong way** — sign error; flip `PAN_SIGN`/`TILT_SIGN` in `ServoDriver` (that's
  what the Phase-1 teleop script is for).
- **Servo strains / buzzes and won't settle at a tilt or pan extreme** — it's being commanded past
  its mechanical limit. Narrow the offending `*_MIN_DEG`/`*_MAX_DEG` in `servo.py` to the angle where
  it still moved freely (see *Servo calibration*).
- **Ports blocked** — default Raspberry Pi OS has no firewall; if you enabled `ufw`, open UDP 9000
  and TCP 8000.

## Updating the Pi

```bash
cd <repo>/turret && git pull && uv sync
```
Deploy note: run `turret` under **systemd** (`Restart=on-failure`) for a hands-off actuator; the
listener's session-gap recovery already handles the Mac tracker restarting (its `seq` resets to 1).
