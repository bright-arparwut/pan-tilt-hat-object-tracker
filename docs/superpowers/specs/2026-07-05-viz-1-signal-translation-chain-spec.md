# Viz ① — Signal-Translation Chain ("how a command becomes motion")

**Date:** 2026-07-05
**Status:** Ready to build (own session).
**Read first:** `2026-07-05-viz-shared-identity.md` — it holds the visual system, the hard Artifact
constraints, and the full grounded fact base. This spec only describes what makes diagram ① unique.

## One-line job
Show a reader **exactly how a single Aim Command turns into physical servo motion** by walking one
concrete value down through every translation layer — making vivid where *our code* stops and the
*library / chip / hardware* take over.

## Audience & takeaway
The builder, asking "why do I need ServoKit — can't ServoDriver just move the servo?" The diagram
answers it visually: a number can't become an electrical pulse without passing through several
layers, and each layer speaks a different language (degrees → microseconds → duty → 12-bit ticks →
I²C bytes → PWM pulse → shaft angle).

## What it must show — the chain (left-to-right on wide screens, top-to-bottom when stacked)

A single, unmistakable **pipeline of 6 stages**, each a card/segment showing **what it receives →
what it does → what it emits**, with the concrete value transforming at every hop. Use the worked
example from the shared fact base (current pan **45°**, command **pan_delta = +2.0°**):

1. **Aim Command** — `pan_delta = +2.0°` — a *relative* nudge, arriving from the Mac over UDP
   (port 9000). Tag amber (it's the command/down path).
2. **ServoDriver** *(our code — highlight this ownership)* — `45° + 2° = 47°`, then `clamp_angles`
   (limits 0–180°) → **`47°` absolute**. Owns: relative→absolute accumulation, clamp, sign, the
   current pose. Emits a single call: `kit.servo[0].angle = 47`.
3. **ServoKit / pca9685** *(downloaded library)* — `47°` → pulse width `≈ 1022 µs`
   (`500 + 47/180 × 2000`) → duty `5.1%` at 50 Hz → 12-bit tick `≈ 209` → I²C register writes
   (`LED0_ON=0`, `LED0_OFF=209`).
4. **I²C bus** — the register bytes travel to address **`0x40`** (2-wire: SDA/SCL).
5. **PCA9685** *(chip on the HAT)* — emits a **~1022 µs HIGH pulse every 20 ms** (50 Hz) on channel 0.
6. **Servo** *(the motor)* — its internal circuit maps pulse width → **shaft ≈ 47°**. Motion.

## The one idea to make visually loud
**The "degrees boundary."** Draw a clear divider (a labeled line / color shift / "handoff" marker)
between stage 2 and stage 3: *"Our code produces 47°. Everything below this line is the library, the
chip, and physics."* This is the payload of the whole diagram — don't let it be subtle.

Secondary cue: annotate each stage with the **"language" it speaks** (degrees · microseconds · duty%
· 12-bit ticks · I²C bytes · PWM pulse · mechanical angle) as a small mono label, so the reader sees
the representation changing at every hop.

## Layout guidance
- A prominent horizontal chain of 6 connected stages with arrowheads carrying the transforming
  value between them (e.g. the value `47°` literally sitting on the arrow from stage 2→3). On narrow
  screens the chain becomes vertical; the connecting arrows re-flow. Wrap the chain in an
  `overflow-x:auto` container so it never breaks the body layout.
- Give stages 1–2 an amber/our-code treatment, 3 a "library" treatment, 4–6 a chip/hardware
  treatment — a subtle palette progression from software (amber/teal) toward hardware (muted/steel),
  reinforcing the descent from abstraction to electrons.
- Optional supporting panel: a tiny "constants" card (servo 0–180°, pulse ~500–2500 µs, 50 Hz /
  20 000 µs period, PCA9685 12-bit / 4096 steps) so the arithmetic is checkable.
- Optional closing line: the printer-driver analogy in one sentence — *ServoDriver is your app's
  "print this pose"; ServoKit is the printer driver for the PCA9685.*

## Out of scope
The video/up path, the full feedback loop, ByteTrack/YOLO internals. This diagram is **only** the
downhill command→motion chain. (Those live in diagrams ② and ③.)
