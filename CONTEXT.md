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
honours those is the backend's business. The YOLO backend also hosts the [Tracker]: a sibling
`track()` runs `model.track()` under `--track` (ADR-0012), leaving `detect()` identity-free.
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
A persistent identity (`tracker_id`) that the [Tracker] assigns to a series of
Detections judged to be the same object across consecutive frames. Lives only while
tracking is enabled (`--track`); the [Detector]'s `detect()` emits identity-free Detections,
while the backend's `track()` is what carries the id (ADR-0012).
_Avoid_: tracklet (bare), object id, trace (that is the drawn trail)

**Tracker**:
The multi-object tracking algorithm that assigns [Track] ids, selected by `--tracker`
(`bytetrack` | `botsort` | `ocsort` | `deepocsort` | `fasttracker` | `tracktrack`) and run
via Ultralytics `model.track(frame, persist=True)` inside the YOLO [Detector Backend]'s
`track()`. `supervision` is no longer the tracking engine — only the annotator (ADR-0012,
superseding the `sv.ByteTrack`-in-loop of ADR-0006).
_Avoid_: ByteTrack (as the only option), sv.ByteTrack, tracking engine

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
Under `--no-track` it records every raw Detection (recall-first, ADR-0004); under `--track`
it records the single tracked population [the Tracker] returns, each row carrying its
`tracker_id` (ADR-0012).
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
drawn black (held for `--track-buffer` frames); the slot is freed for a new Track once that
hold elapses (ADR-0007). The buffer is meant to mirror the [Tracker]'s own lost-track window
so the slot persists exactly as long as the id can revive (ADR-0012).
_Avoid_: cell, window, lane

**Appearance**:
The non-CLI styling surface for the [Annotated Video]: the [Detection Style] and palette, label
and [Track]-trace palette, line and text dimensions, label and trace anchoring, and the [Zoom
Inset]'s colours and proportions. Lives as constants in `config.py` under an `Appearance`
banner — deliberately not `--flags`, not a separate file, and not an external config format
(ADR-0011) — read by a small `annotators.py` factory. Every default reproduces the prior
output, so editing a constant is the only thing that changes the look.
_Avoid_: settings, theme, style, config (config is run *behaviour*)

**Detection Style**:
The selectable way each [Detection] is drawn — one [Appearance] constant (`DETECTION_STYLE`)
picking a supervision annotator: a box outline (`BOX`, `ROUND`, `CORNER`, `CIRCLE`, `ELLIPSE`),
a fill or marker (`COLOR`, `DOT`, `TRIANGLE`), or an anonymising pixel-effect (`BLUR`,
`PIXELATE`). One style at a time, shared by both modes; the default (`BOX`) reproduces the prior
output. The styles share no constructor, so `annotators.py` builds each its own way. Mask-based
shapes (mask/polygon/halo) are out of scope — the [Detector] emits no segmentation to draw them
from (and `halo` would silently draw nothing); see ADR-0011.
_Avoid_: box style, box type, shape (bare), annotator style

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

### Actuation & turret (visual servoing, ADR-0013)

**Actuator Sink**:
The [Frame Sink] that, instead of drawing a frame, consumes its [Track]s and drives a physical
[Turret] to keep the followed [Track] centred. Composes with the [Live Preview] and recorder like
any sink (ADR-0013); the [Detection Loop] never knows it is aiming a motor. Host-side (the Mac is
the brain); the Pi-side servo driver / frame streamer / command listener live outside this loop.
_Avoid_: motor sink, servo sink, tracker (that is the [Tracker])

**Turret**:
The physical pan-tilt platform — Raspberry Pi 5 + Waveshare Pan-Tilt HAT + a USB camera mounted
*on* the platform — that the [Actuator Sink] aims. Because the camera rides the platform, aiming
and seeing form one closed loop (visual servoing). The Pi is the actuator only; detection runs on
the host (ADR-0013).
_Avoid_: gimbal, mount (bare), pan-tilt (bare — that is the HAT)

**Target Selector**:
The pure host-side unit that picks which [Track] the [Actuator Sink] follows. Policy:
**lock-first-id** — latch onto the first stable [Track] `#id` seen and follow it until the [Track]
is lost, then re-latch. Deterministic, no per-frame target flip-flopping (ADR-0013).
_Avoid_: chooser, filter (that is the [Tracker]'s recall role, ADR-0004)

**Aim Controller**:
The pure host-side unit that maps the followed [Track]'s pixel offset from frame centre — the
error — to an [Aim Command]. Proportional first; PID once the P-only loop is seen to overshoot,
because a network sits inside the loop (~50–200 ms) and a naive snap oscillates (ADR-0013).
_Avoid_: PID (bare — PID is one stage of the Controller), servo controller

**Aim Command**:
The `(pan_delta, tilt_delta)` the [Aim Controller] emits and ships to the [Turret]'s Pi over a
simple socket. A relative nudge, not an absolute pose; the Pi clamps it to the servos' mechanical
limits before moving.
_Avoid_: move, servo command (bare), pose
