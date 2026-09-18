# Week 6 — ByteTrack & `model.track()`

**Hours:** 6 · **Where:** Mac · **Milestone:** `--track` with stable `#id` labels and trails

## Why this week

You have a tracker that works badly. Now meet one that works, and understand **precisely
which idea** makes the difference.

ByteTrack's insight is almost embarrassingly simple: *don't throw away the low-confidence
detections.* Everyone else matched high-confidence boxes and discarded the rest. ByteTrack
does a **second association pass** using the leftovers, because a partially-occluded object
produces exactly that — a low-confidence box that a threshold would delete, orphaning the
track. That one extra pass is most of the paper.

## Concepts

- **Two-stage association.** Pass 1: high-confidence detections against all tracks. Pass 2:
  the *remaining* tracks against the **low**-confidence detections. Understand what pass 2
  rescues that your week-5 tracker lost.
- **`track_buffer`** — how many frames a lost track survives before deletion. ByteTrack ships
  30. Note that this project's `DEFAULT_TRACK_BUFFER` is 60, and it's used for something
  *else* (the zoom slot hold, week 7) — read the comment about why they're meant to mirror.
- **Where the tracker lives.** This project runs `model.track(frame, persist=True)` — the
  tracker is **inside** the Ultralytics call, not a separate in-loop object. That's ADR-0012
  *superseding* ADR-0006. Read both. Understanding why a design was replaced is worth more
  than understanding the design.
- **`persist=True`.** What breaks without it? (Try it. The answer is instructive.)
- **Why `--track` and `--slice` don't combine.** `model.track()` runs the model itself, so
  there's no seam for the slicer to wrap. Understand this as a *consequence* of the ADR-0012
  design, not an arbitrary restriction.
- **The second Protocol.** `TrackingDetector.track()` sits beside `Detector.detect()`. Why two
  Protocols rather than one method with a boolean?

## Sessions

**Session 1 (2h) — the seam.** `detection/base.py`'s `TrackingDetector`. `YoloDetector.track()`.
`build_detector`'s tracking branch (never wrap in `SlicedDetector` when tracking). `TrackerKind`
enum wiring. `TrackConfig`.

**Session 2 (2h) — the track view.** `tracking.py`: `_build_track_annotators` (coloured by
`tracker_id`, not `class_id` — `sv.ColorLookup.TRACK`), `_annotate_confirmed` (trail + box +
`#id`), `_present_centers`. Note the `float()` coercion in `_present_centers` and its comment —
that's a real bug someone hit, preserved as a warning for week 11.

**Session 3 (2h) — compare.** Same clip, same crossing objects as week 5. Count id switches
with ByteTrack. Compare to your number. Then try `--tracker botsort` and compare again.

## Files you implement

| File | What |
|---|---|
| `object_tracker/detection/base.py` | `TrackingDetector` Protocol |
| `object_tracker/detection/yolo.py` | `YoloDetector.track()` |
| `object_tracker/detection/__init__.py` | the tracking branch in `build_detector` |
| `object_tracker/tracking.py` | all of it except `ZoomSlots` wiring |
| `object_tracker/config.py` | `TrackConfig` |
| `object_tracker/pipeline.py` | the tracking branch |
| `object_tracker/sidecar.py` | `with_track_id=True` path |

## Tests you're given

`tests/test_tracking.py::test_present_centers_returns_python_floats_not_numpy`,
`::test_annotate_confirmed_is_a_noop_without_tracker_ids`,
`tests/test_detection.py::test_build_detector_never_wraps_the_tracking_path_in_the_slicer`

The first one looks trivial and is not. Find out what it's protecting against (the docstring
tells you; week 11 is where it would have bitten).

## Tests you write

- The sidecar carries `track_id` under `--track` and omits the key under `--no-track`
- A frame where `tracker_id` is `None` (detections present, ids not yet assigned)
- `TrackerKind` round-trips through the CLI string

## Milestone

```bash
uv run track --source ../footage/clip.mp4 --track --tracker bytetrack
```

Stable `#id` labels with motion trails. Ids should survive a brief occlusion.

## ADR to write

**ADR-0006** (ByteTrack in-loop via supervision) and **ADR-0012** (superseded: tracking via
`model.track()`). Write 0006 as if it's your current design, then write 0012 as the document
that replaces it. Learning to *supersede* an ADR rather than edit it is the actual skill.
