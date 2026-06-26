# object-tracker

A pipeline for detecting and tracking objects in video. A backend-agnostic detector
(YOLO today) runs over each frame — optionally under sliced inference so small objects
survive at native resolution — and an in-loop tracker assigns identities, producing an
annotated output video and a machine-readable detections record. Any class, any weights;
birds are just one example. The same loop runs **Offline** over a video file or **Live**
from a camera or stream.

## Language

**Detector**:
The component that, given one frame, returns that frame's Detections —
`detect(frame) -> sv.Detections`. A backend-agnostic interface: the rest of the pipeline
depends only on this contract, never on which model produced the boxes.
_Avoid_: model (bare), predictor, inferer

**Detector Backend**:
A concrete [Detector] wrapping one detection model (YOLO today; DETR / RF-DETR are
candidates later). Owns its own confidence threshold, class filter, and device — how it
honours those is the backend's business.
_Avoid_: engine, model wrapper

**Sliced Detector**:
A [Detector] that wraps another [Detector] and runs it over the [Slice]s of a frame,
merging the per-slice results — the [Sliced Inference] technique realised as a decorator.
Backend-agnostic: it slices for whatever Detector it wraps (ADR-0009).
_Avoid_: slicer (bare), tiler, SAHI detector

**Detection**:
A single object instance found in one frame — bounding box (`xyxy`), confidence, and
class id. The [Detector]'s output unit. Carries no identity of its own; when tracking is on, a
[Track] is what links Detections of the same object across frames (the `tracker_id` is
attached to the Detection, not part of what makes it a Detection).
_Avoid_: hit, box (bare), prediction

**Track**:
A persistent identity (`tracker_id`) that `sv.ByteTrack` assigns to a series of
Detections judged to be the same object across consecutive frames. Lives only while
tracking is enabled (`--track`); the [Detector] itself emits identity-free Detections.
_Avoid_: tracklet (bare), object id, trace (that is the drawn trail)

**Detection Loop**:
The per-frame cycle that reads a frame from a [Frame Source], runs the [Detector], optionally
tracks, and hands the annotated frame to a [Frame Sink] — optionally writing detection records
alongside. Source- and sink-agnostic: the same loop serves [Offline Mode] and [Live Mode].

**Sliced Inference**:
Running the [Detector] on overlapping sub-regions of a frame and merging the results,
so small objects survive at native resolution. The SAHI *technique*, implemented here as a
[Sliced Detector] over supervision's `InferenceSlicer` (not the obss/sahi package — see
ADR-0003).
_Avoid_: tiling (bare), SAHI (as a verb), SAHI (meaning the package)

**Slice**:
One overlapping sub-region of a frame that the [Detector] runs on during sliced inference.
_Avoid_: tile, patch, crop

**Annotated Video**:
The human-facing output: the source video with each frame's Detections (or, under
`--track`, confirmed Tracks) drawn on — box, class/id, confidence.
_Avoid_: result video, output (bare)

**Detections Sidecar**:
The machine-facing output: a per-frame, append-only record of every Detection in a
run (one JSON object per frame — frame index plus its list of Detections), written
beside the Annotated Video. The tracker-ready handoff a downstream consumer can read.
_Avoid_: log, dump, results file

**Zoom Panel**:
One magnified picture-in-picture crop composited into the Annotated Video, centred on a
single Detection so that a very small object is legible.
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

### Sources, sinks & modes (Live vs Offline, ADR-0010)

**Frame Source**:
The seam the [Detection Loop] reads frames from: it yields frames and exposes the run's
resolution, frame rate, and total frame count (absent when unbounded). A backend-agnostic
interface mirroring [Detector] — the loop never knows whether frames come from a file or a
camera.
_Avoid_: reader, capture (bare), input

**File Source**:
A [Frame Source] over a finite video file — the original offline path. Has a known frame
count and frame rate; the loop runs to end-of-file.
_Avoid_: video (bare), clip source

**Live Source**:
A [Frame Source] over a camera (by index) or a stream URL — unbounded, with no total frame
count and a frame rate that may only be nominal. Frames arrive in real time whether or not
the loop is ready, so a slow loop sees growing latency or driver-dropped frames, and the
frame index counts *received* frames, not wall-clock time.
_Avoid_: realtime source, camera (bare — a stream URL is also a Live Source)

**Frame Sink**:
The seam the [Detection Loop] hands each annotated frame to: `show(frame) -> keep_going`,
where a false return ends the run (e.g. the viewer quit). A backend-agnostic interface — the
loop never knows whether the frame is written to a file or shown on screen, and sinks
compose (a [Live Preview] plus a file recorder).
_Avoid_: writer, output (bare), display

**Live Preview**:
The [Frame Sink] that shows annotated frames in an on-screen window — the primary output in
[Live Mode]. Closing the window or pressing `q` ends the run.
_Avoid_: viewer, monitor, display (bare)

**Offline Mode**:
The run shape over a [File Source]: process a finite video to completion, producing an
[Annotated Video] and a [Detections Sidecar]. Chosen by source type, not a flag.
_Avoid_: batch mode

**Live Mode**:
The run shape over a [Live Source]: process frames as they arrive and show a [Live Preview],
running until the viewer quits. Chosen by source type, not a flag. Writes nothing to disk
unless asked.
_Avoid_: realtime mode
