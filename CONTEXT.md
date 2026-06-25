# yolo-byteTrack-sot

A pipeline for detecting (and later tracking) small objects in video using a YOLO
detector run under SAHI sliced inference, producing an annotated output video.

## Language

**Detection**:
A single object instance found in one frame — bounding box (`xyxy`), confidence, and
class id. The loop's output unit. Carries no identity of its own; when tracking is on, a
[Track] is what links Detections of the same object across frames (the `tracker_id` is
attached to the Detection, not part of what makes it a Detection).
_Avoid_: hit, box (bare), prediction

**Track**:
A persistent identity (`tracker_id`) that `sv.ByteTrack` assigns to a series of
Detections judged to be the same object across consecutive frames. Lives only while
tracking is enabled (`--track`); the detector itself emits identity-free Detections.
_Avoid_: tracklet (bare), object id, trace (that is the drawn trail)

**Detection Loop**:
The per-frame cycle that reads a frame, runs sliced inference, and writes results
(annotated video and/or detection records).

**Sliced Inference**:
Running the detector on overlapping sub-regions of a frame and merging the results,
so small objects survive at native resolution. The SAHI *technique*, implemented here
via supervision's `InferenceSlicer` (not the obss/sahi package — see ADR-0003).
_Avoid_: tiling (bare), SAHI (as a verb), SAHI (meaning the package)

**Slice**:
One overlapping sub-region of a frame that the detector runs on during sliced inference.
_Avoid_: tile, patch, crop

**Annotated Video**:
The human-facing output: the source video with each frame's Detections drawn on
(box, class, confidence).
_Avoid_: result video, output (bare)

**Detections Sidecar**:
The machine-facing output: a per-frame, append-only record of every Detection in a
run (one JSON object per frame — frame index plus its list of Detections), written
beside the Annotated Video. The tracker-ready handoff a future tracking stage consumes.
_Avoid_: log, dump, results file

**Zoom Panel**:
One magnified picture-in-picture crop composited into the Annotated Video, centred on a
single Detection so that a very small bird is legible.
_Avoid_: PiP (bare), zoom window, magnifier

**Zoom Inset**:
The set of up to N Zoom Panels composited into the Annotated Video as a right-edge strip.
It has two modes, set by whether tracking is on:
- _Confidence mode_ (`--no-track`): each frame's N highest-confidence Detections, panels
  confidence-ordered, reflecting only the current frame — no cross-frame identity, panels
  may reorder/flicker (ADR-0005). At N=1, a single panel on the top-confidence Detection.
- _Identity mode_ (`--track`): each panel is bound to a [Track] and owns a fixed [Zoom
  Slot] (ADR-0007). Slots fill in first-seen order (or a single forced id via
  `--zoom-track-id`); a panel whose Track is missing this frame renders black in place.
_Avoid_: PiP (bare), zoom window, magnifier, panel wall

**Zoom Slot**:
A fixed position in the identity-mode Zoom Inset, bound to one [Track] for the life of
that Track. The strip never reflows: while the Track is temporarily missing the slot is
drawn black (held through ByteTrack's lost-track buffer); the slot is freed for a new
Track only once ByteTrack truly drops the id (ADR-0007).
_Avoid_: cell, window, lane
