# Week 7 — Identity-aware rendering (the slot state machine)

**Hours:** 6 · **Where:** Mac · **Milestone:** zoom panels pinned to ids, no reflow

## Why this week

A small object is legible in a 4K frame only if you magnify it. But a picture-in-picture strip
raises a question that has nothing to do with pixels: **when there are three objects and two
panels, who gets a panel — and what happens when one disappears for six frames?**

That's a resource-ownership state machine, and it's the same shape as a connection pool, a
worker slot table, or a UI virtual list. The cv2 crop-and-paste arithmetic is given to you;
**the state machine is the lesson.**

## Concepts

- **Two modes, one strip.** Without tracking there's no identity, so panels can only be
  "this frame's top-N by confidence" — which means they **reorder and flicker** (ADR-0005).
  With tracking, each panel binds to an id and **owns a fixed slot** (ADR-0007). Read both
  ADRs: the second exists because the first was unsatisfying.
- **Slot ownership.** A slot is claimed by a track, held while the track lives, drawn **black**
  while the track is briefly missing, and freed only after `track_buffer` frames. Never
  reflowed — a strip that reshuffles is unreadable.
- **Why the hold window mirrors the tracker's.** If the slot frees before the tracker gives up
  on the id, the id can revive into a *different* slot — visible as a jump. Read the
  `DEFAULT_TRACK_BUFFER` comment in `config.py`.
- **Smallest-id-first as "first seen."** `ZoomSlots` fills slots by smallest present id, because
  tracker ids are monotonic. `target_selector` (week 11) uses the identical trick. Notice the
  repeated idiom — that's the codebase teaching you its own vocabulary.
- **EMA smoothing.** The crop centre is exponentially smoothed so the panel doesn't jitter.
  Given to you, but understand `alpha`: lower = smoother = laggier.

## Sessions

**Session 1 (2.5h) — the machine.** `ZoomSlots`: `update(present_centers, frame_idx) -> renders`.
Pure decision logic, no pixels. Claim, hold, black-out, release, `forced_id`. Test it entirely
with dicts and ints — **no images in these tests at all.** If you find yourself needing a numpy
array to test the slot logic, the split is wrong.

**Session 2 (2h) — confidence mode.** `top_centers`, `_confidence_zoom`, `_smooth_center`. The
simpler mode, built second, so you appreciate what identity bought you.

**Session 3 (1.5h) — compositing.** `draw_identity_panels` and `_draw_one_panel` — crop, resize,
border, label, paste into the right-edge strip. Mostly given; wire it up and tune
`ZOOM_PANEL_FRACTION` until it looks right.

## Files you implement

| File | What |
|---|---|
| `object_tracker/zoom.py` | `ZoomSlots`, `top_centers`, `_confidence_zoom`, panel drawing |
| `object_tracker/tracking.py` | `_TrackRuntime`, `_build_track_runtime` |
| `object_tracker/config.py` | `ZoomConfig.track_id` |
| `object_tracker/cli.py` | `--zoom`, `--zoom-size`, `--zoom-max`, `--zoom-track-id`, `--track-buffer` |

## Tests you're given

`tests/test_zoom.py::test_a_track_keeps_its_slot_across_frames`,
`::test_a_missing_track_holds_its_slot_black_for_the_buffer`,
`::test_a_slot_is_freed_for_a_new_track_after_the_hold_elapses`,
`::test_forced_track_id_pins_the_only_slot`

## Tests you write

- More present tracks than slots → the extras get nothing, and the *same* extras stay excluded
- A track that vanishes and revives **within** the hold → same slot, no reflow
- `top_centers` with fewer detections than `n`
- `top_centers` when `confidence` is `None`

## Milestone

```bash
uv run track --source ../footage/clip.mp4 --track --zoom --zoom-max 3
uv run track --source ../footage/clip.mp4 --track --zoom --zoom-track-id 7
```

Watch a panel go black when its object leaves, and come back in the *same* slot.

## ADR to write

**ADR-0005** (zoom inset: no cross-frame association) then **ADR-0007** (identity zoom, fixed
slots). Same pairing exercise as week 6 — write the limited design honestly, then the one that
supersedes it.
