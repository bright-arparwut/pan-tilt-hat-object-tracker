# Identity-mode Zoom Inset: id-pinned fixed slots, black-on-missing

Reverses ADR-0005 **for the `--track` path only**. ADR-0005 still governs the `--no-track`
(confidence-mode) inset unchanged.

When tracking is on, the Zoom Inset stops being a per-frame confidence ranking and becomes
a set of **identity-pinned Zoom Slots**. ADR-0005 deliberately refused cross-frame
association and pointed forward: "If smooth, identity-stable panels are needed, drive them
from the tracker's `tracker_id`s once that stage exists." That stage now exists (ADR-0006),
so we do exactly that — the identity comes from `sv.ByteTrack`, not a hand-rolled IoU
matcher, so ADR-0005's objection (duplicating/pre-empting the tracker) no longer applies.

## Behaviour

- Each [Zoom Slot] is bound to one `tracker_id` and holds a **fixed position**; the strip
  never reflows.
- Slots fill in **first-seen order**, capped at `--zoom-max`. `--zoom-track-id K` overrides
  this with a single slot locked to id `K` (the single-object-tracking mode; implies
  `--track`).
- A slot whose Track has **no detection this frame** renders **black in place** (it does not
  collapse or hold the last crop).
- A black slot is held while the Track is merely lost-but-alive — i.e. within ByteTrack's
  `lost_track_buffer` (`--track-buffer`) — so a brief occlusion keeps the same bird's slot
  and it snaps back on reappearance. The slot is **freed for a new Track only once ByteTrack
  truly drops the id**. The zoom layer tracks `last_seen[id]` itself and shares the
  `lost_track_buffer` value with the tracker to decide this.

## Trade-offs / implications

- This is the opposite of ADR-0005's WYSIWYG, no-hold-last, confidence-ordered strip — by
  design, and only under `--track`. Panels are now stable, identity-true, and label which
  bird they follow.
- Slot reuse is bounded by `--zoom-max`: when all slots hold live-or-recently-lost Tracks, a
  new bird gets no panel until a slot is freed. First-seen wins.
- A `--zoom-track-id K` that never appears yields an inset that draws nothing until `K` is
  first seen, then follows it (black when missing) per the rules above.
- Do **not** reintroduce confidence reordering or per-frame reflow on the `--track` path —
  that throws away the identity stability this ADR exists to provide.
