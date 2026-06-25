# yolo-byteTrack-sot

A pipeline for detecting (and later tracking) small objects in video using a YOLO
detector run under SAHI sliced inference, producing an annotated output video.

## Language

**Detection**:
A single object instance found in one frame — bounding box (`xyxy`), confidence, and
class id. The loop's output unit, kept independent of any tracker.
_Avoid_: hit, box (bare), prediction

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

**Zoom Inset**:
A picture-in-picture panel composited into the Annotated Video showing a magnified
view of a single region, centred (with temporal smoothing) on the highest-confidence
Detection so that very small birds are legible. Shows one region only, by design.
_Avoid_: PiP (bare), zoom window, magnifier
