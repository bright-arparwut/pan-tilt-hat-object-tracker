# Detection loop emits standalone detections; tracking deferred

> **Revised by ADR-0006.** Tracking is no longer deferred: it runs in the loop via
> `sv.ByteTrack` (still *not* `model.track()`, for the reason below). The sidecar keeps its
> standalone raw detections and merely gains a nullable `track_id`. The slicing-vs-native-
> tracker rationale below is exactly why we chose `sv.ByteTrack`.

The detection loop runs YOLO under SAHI sliced inference and emits per-frame
detections in a self-contained format (bbox `xyxy` + confidence + class id) rather
than using Ultralytics' built-in `model.track()`. We do this because SAHI's merged
sliced predictions are not whole-frame YOLO `Results`, so the native tracker cannot
consume them. Keeping detections decoupled lets an external ByteTrack/SOT stage
(implied by the repo name) be added later without reworking the loop.
