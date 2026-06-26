# Tracking runs in the loop via sv.ByteTrack (not yolo.track); sidecar keeps raw rows + nullable track_id

> **Status: superseded by ADR-0012.** Once supervision-based sliced inference was dropped,
> the "sliced-merge constraint" this ADR cites as the reason for `sv.ByteTrack` over
> `model.track()` no longer held — exactly the "future-phase decision" reserved below. ADR-0012
> moves tracking to Ultralytics `model.track()` (six selectable trackers) and keeps supervision
> for annotation only. The sidecar's two-population contract here now applies only to
> `--no-track` (see ADR-0004's amendment).

Revises ADR-0001 (which deferred tracking and rejected `model.track()`).

The detection loop now runs an optional tracking stage **inside** the loop, behind a
`--track` toggle (default on). It uses `supervision`'s `sv.ByteTrack`, fed the per-frame
`sv.Detections`, **not** Ultralytics `model.track()`.

## Why sv.ByteTrack and not yolo.track()

`model.track()` only consumes whole-frame YOLO `Results`. Under sliced inference the
`InferenceSlicer` merges per-slice predictions into a fresh `sv.Detections`, which the
native tracker cannot ingest — the exact reason ADR-0001 deferred tracking. `sv.ByteTrack`
takes any `sv.Detections` (sliced-merged or whole-frame) via
`update_with_detections()` and returns them with `.tracker_id`. Tracking therefore works on
**both** the `--slice` and `--no-slice` paths and preserves the loop invariant that nothing
downstream branches on slicing. The repo name (`yolo-byteTrack-sot`) and ADR-0001's
"external ByteTrack stage" always anticipated this engine; we are pulling it forward, not
swapping it.

## Sidecar contract: raw rows preserved, identity added as a nullable field

`sv.ByteTrack.update_with_detections()` returns only **confirmed** tracks — it drops
recall-first noise (verified: a conf-0.16 static box is dropped every frame). Writing that
filtered subset to the sidecar would silently gut ADR-0004 ("a noisy sidecar is by
design"). So the sidecar still emits **every raw detection**; we only **add** a `track_id`
field (int when the row belongs to a confirmed track, else `null`). Under `--no-track` the
field is omitted entirely, leaving today's sidecar byte-for-byte unchanged.

The id is joined back onto the raw rows without fuzzy box-matching: we stash a row index in
`detections.data["_idx"]` before `update_with_detections`, which carries `data` through to
the returned subset, giving an exact `raw_row → track_id` map (verified).

## Video, under --track

The annotated video draws **only confirmed tracks**, each labelled `#tracker_id`
(`sv.LabelAnnotator`) with short motion trails (`sv.TraceAnnotator`) — the clean, filtered,
identified view that realises ByteTrack as the ADR-0004 false-positive filter on the video,
while the sidecar retains the full raw record. `--no-track` keeps today's all-raw-boxes
annotation.

## Trade-offs / implications

- This changes the **default** output (tracking is on): default video shows confirmed
  tracks + ids + trails, and the default sidecar gains a `track_id` column. Run
  `--no-track` for the legacy standalone-detection behaviour.
- `track_activation_threshold` (`--track-activation`, default 0.25) sits **above** the
  recall-first `--conf` (0.15): only >0.25 detections start tracks while the 0.15–0.25 band
  still helps continue them (the BYTE association trick). This is ADR-0004's false-positive
  filter made concrete; do not conflate it with `--conf`.
- `frame_rate` is taken from the source video; `lost_track_buffer` is exposed as
  `--track-buffer`. `minimum_matching_threshold` and `minimum_consecutive_frames` stay at
  defaults until real footage demands otherwise.
- The standalone-detection handoff ADR-0001 protected still exists: the raw rows (xyxy,
  conf, cls) are all present, so the sidecar can still feed a different external tracker —
  the `track_id` column is purely additive and ignorable.

## Engine availability note (supervision deprecation)

`sv.ByteTrack` is **deprecated since supervision 0.28.0 and removed in 0.30.0** (it emits a
`FutureWarning`; the upstream replacement is `ByteTrackTracker` in the separate `trackers`
package). We deliberately stay on `sv.ByteTrack`: it is present and fully functional in the
locked **0.29.1**, it keeps supervision as the single CV toolkit (ADR-0003), and pulling in
a new tracking dependency was neither grilled nor in scope here. To keep that decision safe
we (a) pin `supervision>=0.25.0,<0.30` in `pyproject.toml` so a dependency bump can't silently
remove the engine, and (b) silence the `FutureWarning` at construction so it doesn't pollute
run output. Migrating to the `trackers` package (or `model.track()` if the sliced-merge
constraint is ever lifted) is a future-phase decision, not this one.
