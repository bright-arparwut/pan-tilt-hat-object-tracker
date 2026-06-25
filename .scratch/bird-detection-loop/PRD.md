# PRD — Bird Detection Loop (YOLO + sliced inference → annotated video + detections sidecar)

## Problem

We need to detect **very small flying birds** in video and produce (a) a legible
annotated video and (b) a machine-readable record of every detection. The detector
must work on small test footage (~384×640) today and scale to high-resolution
(1080p/4K) footage later, and its output must be consumable by a future ByteTrack /
single-object-tracking stage (the repo's eventual goal) without rework.

## Scope

**In scope (this deliverable):**
- A single Python script that runs a detection loop over offline video file(s).
- YOLO detection with an optional sliced-inference path (the SAHI technique).
- Two outputs: an annotated video (with a picture-in-picture zoom inset) and a
  per-frame JSONL detections sidecar.

**Out of scope (future phases):**
- Tracking (ByteTrack) and single-object tracking — deferred; this loop only makes the
  pipeline *tracker-ready* via the sidecar (see ADR-0001).
- Live / real-time stream ingestion — offline files only.
- Model training / fine-tuning — weights are supplied, not produced here.

## Key decisions (see `docs/adr/`)

- **ADR-0001** — Loop emits standalone `sv.Detections` + a JSONL sidecar; we do *not*
  use Ultralytics `model.track()`. The sidecar is the tracker handoff.
- **ADR-0002** — Sliced inference retained for high-res target footage; it is a runtime
  toggle (`--slice/--no-slice`) so the same script runs plain whole-frame YOLO on the
  small test clip and sliced inference on real footage.
- **ADR-0003** — Sliced inference uses `supervision`'s `sv.InferenceSlicer`, not the
  obss/sahi package. "SAHI" here means the *technique*. supervision is the single CV
  toolkit (slicing + annotation + video sink + future ByteTrack).
- **ADR-0004** — Recall-first detection (low `--conf` ~0.15); the future tracker is the
  false-positive filter. A noisy sidecar is *by design*.

## Pipeline / data flow

```
video file ─▶ frame loop (sv.get_video_frames_generator)
                 │
                 ▼
        detect(frame) ──▶ sv.Detections            ← slicing toggle lives here
          ├─ --slice    : sv.InferenceSlicer(callback=YOLO-per-slice, NMS)
          └─ --no-slice : model(frame) → sv.Detections.from_ultralytics
                 │
                 ├─▶ class filter (--classes; default bird/14 for COCO)
                 ▼
        ┌────────┴─────────┐
        ▼                  ▼
  annotate frame      append to sidecar (JSONL)
  (boxes + zoom        {"frame": i, "detections":[...]}
   inset, EMA-smoothed
   on top-conf bird)
        ▼
  sv.VideoSink.write_frame
```

Both detect() branches return `sv.Detections`, so everything downstream (annotation,
sidecar, zoom inset, future ByteTrack) is identical regardless of path.

## CLI surface

| Flag | Default | Purpose |
| --- | --- | --- |
| `--source` | (required) | Input video path |
| `--weights` | COCO-pretrained (e.g. `yolo11n.pt`) | YOLO weights; custom `.pt` drops in |
| `--device` | auto (cuda→mps→cpu) | Inference device override |
| `--conf` | `0.15` | Confidence threshold (recall-first, ADR-0004) |
| `--classes` | `bird` (id 14) for COCO; all for custom | Class filter |
| `--slice / --no-slice` | `--slice` | Toggle sliced inference (ADR-0002) |
| `--slice-wh` | `640 640` | Slice width/height (px) |
| `--overlap-ratio` | `0.2 0.2` | Slice overlap (w, h) |
| `--overlap-filter` | `nms` | Slice merge strategy (`nms`/`nmm`) |
| `--thread-workers` | `4` | Parallel slice inference |
| `--zoom / --no-zoom` | `--zoom` | PiP zoom inset on/off |
| `--zoom-size` | `0.05` | Zoom crop side as a fraction of frame width; magnification = 0.25 / zoom-size (≈5×) |
| `--output` | `<source>.annotated.mp4` | Annotated video path |
| `--sidecar` | `<source>.detections.jsonl` | JSONL sidecar path |

## Outputs

- **Annotated video** (`sv.VideoSink`, source fps/resolution preserved): thin boxes +
  Zoom Inset (PiP magnified view, EMA-smoothed centre on top-confidence detection).
- **Detections sidecar** (JSONL, one object per frame):
  ```json
  {"frame": 0, "detections": [{"xyxy": [x1,y1,x2,y2], "conf": 0.62, "cls": 14, "name": "bird"}]}
  ```
  `xyxy` are pixel coords in source resolution. Frames with no detections still emit a
  line with an empty `detections` list.

## Defaults & behaviour (not separately grilled)

- Process **every** frame (the future tracker needs frame continuity).
- Progress bar via `tqdm`; fail fast if `--source` can't be opened; create output dirs.
- ⚠️ On the 384×640 test clip, default `--slice-wh 640 640` ≥ frame, so no real
  slicing occurs — use `--no-slice` (recommended) or `--slice-wh 256 256` to exercise
  tiling on the test footage.

### Resolution behaviour (works across 384×640 → 1080p → 4K)

The loop is resolution-agnostic by design (ADR-0002):
- Video I/O, slicing, and the sidecar adapt to the source resolution automatically;
  the default `--slice-wh 640 640` is a no-op on the tiny clip but tiles 1080p (~8
  slices) / 4K (~32–35 slices) with no flag changes.
- **Use `--slice` on high-res footage** (default on); `--no-slice` on 4K runs but
  shrinks the whole frame to imgsz and under-detects small birds.
- **All rendering is resolution-relative** — box thickness and zoom crop/panel sizes
  derive from `video_info.resolution_wh`; no fixed-pixel constants.
- **Cost:** high-res + slicing means tens of forward passes per frame → slow offline
  processing; `--thread-workers` and a CUDA GPU matter. Correctness is unaffected.

## Tooling & dependencies

- **`uv`** for dependency management: `pyproject.toml` + committed `uv.lock`.
  Run via `uv run detect-birds --source ...` (console script) or
  `uv run python detect_birds.py ...`. (Alternative considered: PEP 723 inline script
  metadata — rejected for lacking a committed lockfile.)
- Deps: `ultralytics`, `supervision`, `opencv-python`, `numpy`, `tqdm`. Python ≥ 3.10.

## Acceptance criteria

1. `uv run detect-birds --source test.mp4 --no-slice` produces an annotated `.mp4` and a
   `.jsonl` sidecar with one line per frame.
2. `--slice --slice-wh 256 256` runs sliced inference on the same clip and produces the
   same artifact shapes.
3. `--weights custom.pt` loads custom weights and keeps all classes (no forced bird filter).
4. Sidecar lines validate against the schema above; `xyxy` are source-resolution pixels.
5. Zoom inset follows the top-confidence detection and does not teleport frame-to-frame.
6. Bad `--source` exits non-zero with a clear message; no partial/corrupt outputs left.

## Future (next phase, not now)

Add a tracking stage that consumes the sidecar (or the in-memory `sv.Detections`) via
`sv.ByteTrack`, drawing `tracker_id`s and `sv.TraceAnnotator` trails on the video. This
is the false-positive filter referenced in ADR-0004 and the reason for ADR-0001's
standalone-detection contract.
