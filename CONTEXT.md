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

**Zoom Panel**:
One magnified picture-in-picture crop composited into the Annotated Video, centred on a
single Detection so that a very small bird is legible.
_Avoid_: PiP (bare), zoom window, magnifier

**Zoom Inset**:
The set of up to N Zoom Panels composited into the Annotated Video — one per Detection,
chosen as the current frame's highest-confidence Detections (N is configurable; at N=1
it is a single panel on the top-confidence Detection). Reflects only the current frame:
panels carry no cross-frame identity, since associating the same bird across frames is
the tracker's role (ADR-0001).
_Avoid_: PiP (bare), zoom window, magnifier, panel wall
