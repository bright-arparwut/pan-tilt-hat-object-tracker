# Week 5 — Tracking by hand (IoU + greedy assignment)

**Hours:** 7 · **Where:** Mac · **Milestone:** your own tracker holds an id across 100 frames

## Why this week

**This is the highest-value week in the curriculum.** Everything before it is stateless: frame
in, boxes out, no memory. Tracking is where the system first has to *remember*, and remembering
is where every hard problem lives — occlusion, identity switches, birth and death of tracks.

You are going to write a tracker by hand before you're allowed to use one. It will be worse
than ByteTrack. That's the point: in week 6 you'll see exactly *which* failure ByteTrack fixes,
instead of treating it as a magic box.

This week's file — `object_tracker/toy_tracker.py` — does **not** exist in the root repo. It's
a scaffold that exists only in the sandbox. You throw it away in week 6, having learned what it
was for.

## Concepts

- **The association problem.** Frame *t* has N boxes, frame *t+1* has M boxes. Which is which?
  That's it. That's tracking.
- **IoU as a matching metric.** Same formula as NMS in week 2, different job: there it
  *suppressed* duplicates within a frame, here it *matches* across frames.
- **Greedy vs optimal (Hungarian) assignment.** Greedy takes the best pair, removes both,
  repeats. Hungarian minimises total cost globally. Build greedy; construct by hand a case
  where it picks wrong.
- **Track lifecycle.** Birth (an unmatched detection), death (an unmatched track, after a
  patience window), and why you don't kill a track on its first miss.
- **The ID switch** — the characteristic tracking failure. Two objects cross; their ids swap.
  Understand why IoU alone can't prevent it.
- **Motion models (read, don't build).** A constant-velocity Kalman filter predicts where a
  track *should* be before matching, which fixes fast motion and brief occlusion. Run the
  provided demo, understand the predict/update cycle, then move on. Building one is this
  week's stretch goal, not its requirement.

## Sessions

**Session 1 (2h) — IoU and the cost matrix.** `iou_matrix(boxes_a, boxes_b) -> np.ndarray`.
Pure, vectorised, ~15 lines. Test it against hand-computed values — including the
non-overlapping case and the identical-box case. Get this exactly right; everything rests on it.

**Session 2 (3h) — the tracker.** `ToyTracker.update(detections) -> detections_with_ids`.
Greedy matching above an IoU threshold, unmatched detections become new tracks, unmatched
tracks age out after `max_age` frames. Thread the state immutably — a frozen dataclass in, a
new one out, matching the project's style.

**Session 3 (2h) — watch it fail.** Run it on real footage with week 3's annotator drawing
`#id`. Find a clip where two objects cross. **Count the id switches.** Write the number down —
week 6 needs it for comparison.

## Files you implement

| File | What |
|---|---|
| `object_tracker/toy_tracker.py` | `iou_matrix`, `ToyTrackerState`, `ToyTracker.update` (sandbox-only) |

## Tests you're given

`tests/test_toy_tracker.py::test_iou_of_identical_boxes_is_one`,
`::test_iou_of_disjoint_boxes_is_zero`,
`::test_a_track_keeps_its_id_while_it_keeps_matching`,
`::test_an_unmatched_track_survives_one_miss_then_dies`

## Tests you write

- A detection with no match above threshold gets a **new** id, not the nearest old one
- Two tracks, two detections, crossed: assert what greedy actually does (document the bug)
- Ids are never reused after a track dies
- Empty frame in, empty out, state ages correctly

## Milestone

```bash
uv run python scripts/replay_toy_tracker.py ../footage/clip.mp4    # provided
# prints: 47 tracks born, 12 id switches over 300 frames
```

## Reading (not building)

`docs/kalman-note.md` in this sandbox walks the predict/update cycle with a runnable 30-line
example. 45 minutes. Understand *why* a motion model helps before week 6 shows you one in
production.

## ADR to write

**ADR-0004 — recall-first detection, tracking as the filter.** Now you know what a tracker
does, the `--conf 0.15` decision from week 2 should make sense. Write down why letting noise
through and filtering it temporally beats raising the threshold.

## Stretch

Add a constant-velocity Kalman filter to `ToyTracker` and re-measure your id-switch count.
Expect a real improvement on fast motion.
