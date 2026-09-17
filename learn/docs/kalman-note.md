# Kalman filters — read, don't build (week 5)

~45 minutes. This is the one place in the curriculum where you deliberately *don't* implement
something. At 5–8 hrs/week, building a Kalman filter from scratch costs a whole week and
teaches one idea. Here is the idea, with a demo you can run.

## The problem it solves

Your week-5 tracker matches by IoU against a track's **last known box**. That fails in two
common cases:

1. **Fast motion.** The object moves further than its own width between frames. IoU is 0.
   The match fails, the track dies, a new id is born. An ID switch, caused by nothing but speed.
2. **Brief occlusion.** The object is behind a lamp post for four frames. When it reappears it
   is nowhere near where it vanished.

The fix in one sentence: **match against where the track is *predicted* to be, not where it
last was.**

## Predict / update

A Kalman filter keeps a *belief* about state — here, `[x, y, w, h, vx, vy, vw, vh]`: the box
plus its velocity. The belief is a mean **and** an uncertainty, and the cycle has two steps:

- **Predict.** Advance the state by the motion model (constant velocity: `x += vx`), and
  *grow* the uncertainty. Time passing makes you less sure.
- **Update.** A detection arrives. Blend prediction and measurement, weighted by their
  relative uncertainties, and *shrink* the uncertainty. Evidence makes you more sure.

That weighting is the whole filter. A confident prediction plus a noisy measurement leans on
the prediction; an uncertain prediction plus a crisp measurement leans on the measurement.
The Kalman gain is the name of that ratio.

## The demo

```bash
uv run python scripts/kalman_demo.py
```

~30 lines, one dimension, no dependencies beyond numpy. An object moves at constant velocity;
measurements are noisy; between frames 10 and 15 the measurements stop entirely (occlusion).
Watch the estimate coast through the gap on velocity alone, and watch the uncertainty grow
while it coasts and collapse when measurements return.

**Things worth noticing:**

1. During the occlusion the estimate keeps moving. That is the whole trick — a dead-reckoned
   position, exactly like the turret's pose estimate in week 12. Same idea, different domain.
2. The uncertainty grows without measurements. That is *why* a track has a `max_age`: past
   some point the prediction is worthless and keeping the track does more harm than good.
3. Change `measurement_noise` and watch the estimate get smoother and laggier. That trade —
   responsiveness against stability — is the same one you tune as `kp` in week 11.

## Where you'll meet it again

- **Week 6:** ByteTrack uses a Kalman filter per track, exactly this way. You are not
  implementing it, but you should know what is happening in there.
- **Week 11:** the EMA-smoothed zoom centre is a crude one-parameter cousin.
- **Week 12:** the turret's dead-reckoned pose is prediction with *no* update step at all —
  no measurement ever arrives. Think about what that means for its uncertainty, and why pan's
  hard limits are so valuable.

## Stretch

Add a constant-velocity filter to `ToyTracker` and re-measure your id-switch count on the
same clip. Predict before matching, update after. Expect a real improvement on fast motion —
and expect it to make *nothing* better on slow, well-separated objects.
