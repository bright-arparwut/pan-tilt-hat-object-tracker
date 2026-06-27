# Tracking via Ultralytics `model.track()`; supervision for annotation only

Supersedes ADR-0006. Under `--track`, the YOLO Detector Backend now assigns identities by
calling Ultralytics `model.track(frame, persist=True, tracker="<name>.yaml")` per frame,
instead of feeding per-frame `sv.Detections` to an in-loop `sv.ByteTrack`. `supervision`
stays the annotator/labeler/trace — it is no longer the tracking engine.

## Why now (the constraint ADR-0006 reserved)

ADR-0006 chose `sv.ByteTrack` *because* `model.track()` could not ingest the
`InferenceSlicer`-merged `sv.Detections`, and it explicitly named "`model.track()` if the
sliced-merge constraint is ever lifted" as a future-phase decision. We are dropping the
supervision-based sliced-inference path (to be reworked later on a YOLO/SAHI
`get_sliced_prediction` path — a separate decision), which lifts that constraint. So we take
the migration ADR-0006 anticipated.

The payoff: Ultralytics ships **six** trackers — `bytetrack`, `botsort`, `ocsort`,
`deepocsort`, `fasttracker`, `tracktrack` — selected by their yaml, where `supervision`
offered only ByteTrack. We get the whole family for free, and we shed the deprecated
`sv.ByteTrack` (removed in supervision 0.30) along with its `FutureWarning` suppression and
the defensive `supervision<0.30` pin's *reason for being* (the pin itself is left alone here;
bumping supervision is out of scope).

## Owned loop, not `model.track(source=...)`

We use the **per-frame** form (`model.track(frame, persist=True)`), **not**
`model.track(source="video.mp4")`. The latter makes Ultralytics own the frame loop, which
would collapse the `FrameSource`/`FrameSink` seams that make Live mode, the on-screen
preview, the sidecar, and composable sinks possible (ADR-0010). `persist=True` keeps tracker
state across our per-frame calls; a fresh model per `run()` means no cross-run id leakage.
The returned `Results` flow through `sv.Detections.from_ultralytics(...)`, which carries
`boxes.id` into `tracker_id` — the bridge that lets supervision keep annotating unchanged.

## Seam shape (ADR-0009 stays intact)

`Detector.detect(frame) -> sv.Detections` stays **identity-free**. A sibling
`TrackingDetector` Protocol (`track(frame) -> sv.Detections`, carrying `tracker_id`) is the
seam the pipeline depends on under `--track`; the YOLO backend implements both. The pipeline
calls `track()` on `--track` and `detect()` on `--no-track`, and only touches `.detect` on the
`--no-track` branch (so a tracking-only backend would work). The old in-loop stage is deleted:
`_track_frame`, `_build_track_map`, the `_ByteTracker` Protocol, and `sv.ByteTrack` itself.
(A richer multi-engine `Tracker` abstraction — several tracker backends fed detections — stays
deferred: Ultralytics trackers can't be driven that way, so YAGNI.)

## Sidecar: one population under `--track`

`model.track()` returns a single set — the tracker's output for the frame — not ADR-0004's
raw-vs-confirmed split. Under `--track` the sidecar now records **that** tracked set, with
`tracker_id` already attached; the `data["_idx"]` → `track_id` join machinery is gone because
ids no longer need to be re-attached to a separate raw layer. ADR-0004's two-population
sidecar (all raw rows + nullable id) now applies **only to the `--no-track` path**. The
recall-first philosophy survives: `--conf 0.15` still rides in via `model.track()`'s predict
step, and the tracker's own `track_high_thresh`/`new_track_thresh` do the filtering.

## Config surface

- **`--tracker`** is an enum (`bytetrack` default — preserving ADR-0006 behavior) mapped to
  the shipped `<name>.yaml`. Tracker choice is run *behavior*, so it is a CLI flag, not an
  Appearance constant (CONTEXT.md).
- **`--track-activation` is removed.** The threshold lives in the tracker yaml; `bytetrack`'s
  shipped `track_high_thresh: 0.25` equals the old default, so default behavior is unchanged.
- **`--track-buffer` is kept**, but solely to size the identity-mode Zoom Slot hold (ADR-0007)
  — it no longer reaches the tracker (we write no yaml). It mirrors the shipped
  `track_buffer: 30`. **Caveat:** pick a tracker whose shipped buffer differs from this value
  and the zoom-slot hold desyncs from the tracker's true id lifetime; only matters away from
  defaults.

## Considered options

- **Separate `Tracker` seam fed detections-in/ids-out** — rejected: Ultralytics trackers run
  the model internally and cannot be driven by externally-produced detections, so this would
  only host `sv.ByteTrack`, defeating the point.
- **Keep both tracking systems** (sv.ByteTrack + Ultralytics) — rejected: doubles the code
  paths and config shapes and keeps the deprecated dependency alive.
- **Generate a per-run override yaml** to preserve `--track-activation`/`--track-buffer` as
  live tracker knobs — rejected for now: `model.track()` has no per-call threshold override,
  the threshold keys differ across the six trackers' schemas (`track_buffer` vs `max_age`,
  etc.), and defaults already match. Not worth the yaml-I/O machinery here.

## Consequences

- **New dependency: `lap`.** Ultralytics's trackers (BoT-SORT/ByteTrack and the rest) do
  their linear assignment via `lap`, which `sv.ByteTrack` bundled but Ultralytics does not.
  It is declared in `pyproject.toml` (`lap>=0.5.12`); without it `model.track()` raises
  `ModuleNotFoundError: No module named 'lap'` on the first frame (Ultralytics's runtime
  auto-install can't be relied on — a `pip`-less venv fails it silently).
- The **default output is unchanged at defaults** (`bytetrack`, conf 0.15, buffer 30).
- Ultralytics derives its tracker's lost-track window from a `frame_rate` it infers
  (defaulting to 30 for bare-frame input), where the old code passed the source fps to
  `sv.ByteTrack(frame_rate=...)`. At non-30 fps the wall-clock hold differs slightly.
- `--slice` + `--track` is no longer possible; moot here because sliced inference is being
  removed and reworked separately.
