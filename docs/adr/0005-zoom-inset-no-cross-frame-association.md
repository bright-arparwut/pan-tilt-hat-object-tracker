# Zoom Inset follows top-N detections with no cross-frame association

> **Reversed by ADR-0007 for the `--track` path only.** This ADR still governs the
> `--no-track` (confidence-mode) inset unchanged. Under `--track`, identity-stable panels
> are driven from `tracker_id`s — exactly the "once that stage exists" escape hatch this
> ADR names below.

The Zoom Inset can follow up to N birds (`--zoom-max`, default 1), rendered as a
right-edge strip of Zoom Panels. Each frame we take the N highest-confidence Detections,
order the panels by confidence, and draw only what that frame contains — fewer
Detections draw fewer panels, and an empty frame draws no strip. We deliberately do
**not** match panels to the previous frame (no nearest-neighbour / IoU association) and
do **not** persist a last-known crop. Only the slot-0 (top-confidence) centre is
EMA-smoothed, inheriting the single-inset behaviour; slots 1+ are drawn raw and may
reorder or flicker as confidences cross between frames.

We accept that flicker on purpose. Associating the same bird across frames is exactly
the job of the future ByteTrack stage (ADR-0001), which owns identity and is the
false-positive filter for the recall-first detector (ADR-0004). Building even a small
greedy matcher here would duplicate and pre-empt that stage, smuggle cross-frame state
into a loop whose contract is standalone per-frame Detections, and tempt us to leak that
identity into the Sidecar. The Inset is a viewing aid, not a tracking guarantee.

Implication for future readers: panel flicker and slot reordering under many
near-threshold Detections are *by design*, not a bug. Do not "fix" them by adding
nearest-neighbour/IoU matching or per-slot persistence in the detection loop — that
reintroduces tracking the architecture deliberately defers (ADR-0001). If smooth,
identity-stable panels are needed, drive them from the tracker's `tracker_id`s once that
stage exists.
