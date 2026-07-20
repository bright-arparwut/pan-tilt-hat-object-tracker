# Viz ③ — Layered Stack ("who owns what")

**Date:** 2026-07-05
**Status:** Ready to build (own session).
**Read first:** `2026-07-05-viz-shared-identity.md` — visual system, hard Artifact constraints, full
grounded fact base. This spec only describes what makes diagram ③ unique.

## One-line job
Show the **four layers between our code and the spinning servo as a labeled stack**, making the
**boundaries** and each layer's ownership explicit: what we write, what we download, what's the chip,
what's the motor — and why each layer exists.

## Audience & takeaway
The builder asking "why not just control it directly?" The stack answers: each layer owns one
concern and speaks one language; you only *write* the top layer, and the rest is either downloaded,
a chip, or physics. Replacing a lower layer means re-implementing something already solved.

## What it must show — four stacked bands, top = our code, bottom = hardware

Render as **four horizontal bands stacked vertically**, with a visible boundary/handoff between each.
Top is closest to us (software we author); each band down is further from our control.

For **each** band show four things: **Name**, **what it owns**, **in → out (the language it speaks)**,
and **"could we replace it?"**.

1. **`ServoDriver`** — *our code (~30 lines)*, status **built-pending** (spec'd, waiting on hardware).
   - Owns: Aim Command semantics — accumulate the *relative* `pan_delta`/`tilt_delta` onto the pose,
     `clamp_angles` to mechanical limits, axis sign, current pose; satisfies the `Servo` Protocol the
     listener calls.
   - In → out: `pan_delta/tilt_delta` (degrees, relative) → `kit.servo[n].angle = <abs degrees>`.
   - Replace? **No** — this is *our* logic, the reason it exists.
2. **`ServoKit` / `adafruit-circuitpython-pca9685`** — *downloaded library*, status **install it**.
   - Owns: degrees → pulse width → duty% → 12-bit tick → the exact **I²C register writes** the
     PCA9685 wants (`MODE1`, `PRESCALE`, `LED0_ON/OFF`…), plus setting the 50 Hz PWM prescaler.
   - In → out: angle in degrees → I²C register bytes to `0x40`.
   - Replace? **Only by badly re-writing it** yourself in raw `smbus2` — more code, more bugs, zero
     benefit.
3. **PCA9685** — *chip on the Waveshare HAT*, status **hardware**.
   - Owns: turning register values into a real **PWM electrical signal** — 16 channels, 12-bit duty,
     50 Hz — independent of the Pi's CPU.
   - In → out: I²C register values → PWM pulse trains on channels 0/1.
   - Replace? **It's hardware.**
4. **Servo** — *the motor*, status **hardware**.
   - Owns: its internal control circuit maps **pulse width → shaft angle** (e.g. ~1.5 ms ≈ center).
   - In → out: a ~500–2500 µs pulse every 20 ms → physical rotation.
   - Replace? **It's the motor.**

## The one idea to make visually loud
**"We only write the top band."** Make band 1 clearly *ours* (accent/solid), and bands 2–4 visibly
*not-ours* (downloaded → chip → physics), with a strong horizontal boundary between band 1 and band
2 — the same "degrees boundary" as diagram ① but expressed as a stack seam. A reader should grasp in
one glance that the vast majority of the stack is downloaded/hardware and our contribution is a thin
adapter on top.

## Layout guidance
- Vertical stack of four full-width bands with clear seams; each band an even, scannable row/grid of
  the four facts (Name · Owns · In→Out · Replace?). Keep the "In→Out" values in monospace.
- Encode ownership in form: band 1 in the accent/"ours" treatment (teal/amber), band 2 in a
  "downloaded/library" treatment, bands 3–4 in a muted "hardware" steel. A small status chip per band
  (`we write` · `we install` · `chip` · `motor`).
- Optional closing analogy card: *ServoDriver = your app's "print this pose"; ServoKit = the printer
  driver for the PCA9685; PCA9685 = the printer's controller; servo = ink on the page.*
- On narrow screens the four-fact row within each band stacks; the bands themselves stay a vertical
  stack. No horizontal body scroll.

## Out of scope
The live data flow / feedback loop (diagram ②) and the fully worked numeric example walking a single
value through (diagram ①). This one is about **layers and boundaries**, not a running command —
though naming the language each layer speaks (degrees / I²C bytes / PWM / mechanical angle) ties the
set together.
