# 08 — In-loop tracking (sv.ByteTrack) + identity-mode Zoom Inset

Status: done (implemented on feat/bird-detection-loop)

## Goal

Pull the deferred tracking stage into the detection loop behind a `--track` toggle, using
`supervision`'s `sv.ByteTrack` (not `model.track()`), and make the Zoom Inset able to
**follow a bird by its `tracker_id`** instead of by per-frame confidence. Tracking is on by
default; `--no-track` reproduces today's behaviour byte-for-byte.

## Decisions (from grilling session)

- **Engine — `sv.ByteTrack`, not `yolo.track()`** (ADR-0006). Feed the existing per-frame
  `sv.Detections` to `byte_track.update_with_detections()`. Works on **both** `--slice` and
  `--no-slice`; `model.track()` can't consume sliced/merged detections (ADR-0001). One
  stateful `sv.ByteTrack` per run, `frame_rate` from the video.
- **Default ON** — `--track`/`--no-track`, default `--track`. Consistent with `--slice`/
  `--zoom`. `--no-track` ⇒ today's output unchanged (no `track_id`, confidence-mode zoom,
  all-raw-box annotation).
- **Sidecar — raw rows + nullable `track_id`** (ADR-0006). `update_with_detections` returns
  only confirmed tracks (it drops recall-first noise — keeping it would violate ADR-0004).
  So keep **every raw detection** and **add** `"track_id": int|null`. Join via
  `detections.data["_idx"]` stashed before tracking (carries through to the returned subset
  → exact `raw_row → track_id` map). Under `--no-track`, omit the field entirely.
- **Annotation under `--track`** — draw **confirmed tracks only**: boxes + `#tracker_id`
  labels (`sv.LabelAnnotator`) + short trails (`sv.TraceAnnotator`). `--no-track` keeps the
  current all-raw-box annotation.
- **Identity-mode Zoom Inset** (ADR-0007, reverses ADR-0005 for `--track`):
  - Each panel is bound to a `tracker_id` in a **fixed [Zoom Slot]**; the strip never
    reflows. Slots fill **first-seen order**, capped at `--zoom-max`.
  - Missing-this-frame ⇒ slot drawn **black in place** (no collapse, no hold-last crop).
  - Black slot **held** while the id is lost-but-alive (within `lost_track_buffer`); slot
    **freed** for a new id only once ByteTrack truly drops it. Zoom layer keeps its own
    `last_seen[id]` and shares the buffer value.
  - **`--zoom-track-id K`** — single slot locked to id `K` (single-object tracking); ignores
    the `--zoom-max` selection; implies `--track`.
  - `--no-track` ⇒ confidence-mode inset, unchanged (ADR-0005).
- **Tracker knobs** — expose `--track-buffer` (`lost_track_buffer`, default 30) and
  `--track-activation` (`track_activation_threshold`, default 0.25, sits above recall-first
  `--conf 0.15`). `frame_rate` from the video; `minimum_matching_threshold` /
  `minimum_consecutive_frames` left at defaults.

## CLI additions

| Flag | Default | Purpose |
| --- | --- | --- |
| `--track / --no-track` | `--track` | Toggle in-loop ByteTrack (ADR-0006) |
| `--track-buffer` | `30` | `lost_track_buffer` — frames a lost id (and its black slot) is held |
| `--track-activation` | `0.25` | `track_activation_threshold` — min conf to start a track |
| `--zoom-track-id` | `None` | Lock the inset to one `tracker_id` (single-object mode; implies `--track`) |

## Tasks

- **Config** — add a `TrackConfig(enabled, activation, buffer)` frozen dataclass; add
  `track_id: int | None` to `ZoomConfig`. Thread both through `run()`.
- **CLI** (`build_parser`): add `--track` (`BooleanOptionalAction`, default `True`),
  `--track-buffer` (`int`, 30), `--track-activation` (`float`, 0.25), `--zoom-track-id`
  (`int`, default `None`).
- **Validation** (`validation_error`): `--track-buffer >= 1`; `0 < --track-activation <= 1`;
  `--zoom-track-id` requires `--track` (error on `--no-track --zoom-track-id`); keep existing
  `--zoom-size` / `--zoom-max` checks.
- **Tracker** — construct one `sv.ByteTrack(track_activation_threshold=..., lost_track_buffer=...,
  frame_rate=video_info.fps)` in `run()`. Per frame, stash `detections.data["_idx"] =
  np.arange(len(detections))`, call `update_with_detections`, build `raw_row → track_id`.
- **Sidecar** (`detection_records`): when tracking, add `"track_id"` (int or `null`) per row
  from the join map; when not tracking, emit today's records unchanged.
- **Annotation** — when tracking, annotate the **confirmed** detections with box + label
  (`#id`) + trace; carry a persistent `sv.TraceAnnotator`. Else current `BoxAnnotator` path.
- **Identity-mode zoom** — new drawer that maintains `slots: list[track_id]` + `last_seen`:
  - assign first-seen ids to free/expired slots (or the single `--zoom-track-id` slot);
  - per slot, if its id is present this frame draw its crop (EMA-smoothed centre per slot),
    else draw a black panel (keep the `#id` label) while `frame - last_seen[id] <= buffer`;
  - drop/free a slot when `frame - last_seen[id] > buffer`.
  Reuse `ZOOM_PANEL_FRACTION`, crop/clamp math, and border from the existing drawer.
- **Tests** (pytest): id-join correctness (incl. noise row → `null`); `--no-track` sidecar
  byte-identical to pre-change; slot lifecycle (hold black through buffer, snap-back on
  reappear, free after buffer); `--zoom-track-id` single-slot lock; validation errors
  (`--no-track --zoom-track-id`, bad `--track-buffer`/`--track-activation`).

## Resolution behaviour

Unchanged contract (ADR-0002): no fixed-pixel constants; panel/crop/label/trace sizes derive
from `video_info.resolution_wh`. `frame_rate` (hence buffer timing) comes from the source.

## Acceptance

1. `--track` (default): sidecar rows gain `track_id` (int on confirmed, `null` on noise),
   every raw row still present; video shows confirmed tracks + `#id` + trails.
2. `--no-track`: annotated video, sidecar (no `track_id` key), and confidence-mode zoom are
   byte-for-byte today's behaviour.
3. `--track --zoom-max 4`: up to 4 id-pinned slots, fixed order; a bird occluded briefly
   keeps its slot (black) and returns to it; a long-gone id frees its slot for a new bird.
4. `--zoom-track-id K`: single inset locked to `K`, black when `K` is missing.
5. Tracking works identically on `--slice` and `--no-slice`.
6. Validation: `--no-track --zoom-track-id 7`, `--track-buffer 0`, `--track-activation 1.5`
   each exit non-zero with a clear message; no partial output.

## Supersedes / doc sync (done in this issue)

- **ADR-0001** revised (tracking no longer deferred) — note added.
- **ADR-0005** reversed for the `--track` path — note added; ADR-0007 written.
- **CONTEXT.md** — added `Track`, `Zoom Slot`; `Zoom Inset` now documents both modes.
- **PRD** — tracking section, CLI rows, acceptance, and "Future" updated.

## Depends on

03 (detection + slicing toggle), 05 (sidecar), 07 (zoom strip + `--zoom-max`).

## Refs

ADR-0006 (ByteTrack in loop), ADR-0007 (identity zoom), ADR-0001/0004/0005. CONTEXT.md
(Track, Zoom Slot, Zoom Inset). PRD §CLI surface, §Outputs, §Future.
