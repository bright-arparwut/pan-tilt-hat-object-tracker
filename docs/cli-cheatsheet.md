# `track` CLI cheat sheet

Quick reference for `uv run track`. Full help: `uv run track --help`.

## The one rule: mode is inferred from `--source`

You never pass a mode flag. The **shape of `--source`** decides it:

| `--source` value | Mode | Example |
| --- | --- | --- |
| a file path | **Offline** | `--source clip.mp4` |
| all digits → camera index | **Live** | `--source 0` |
| a URL (`rtsp:// http:// https:// udp:// tcp://`) → stream | **Live** | `--source rtsp://cam/stream` |

**Offline** writes an annotated `.mp4` + a JSONL sidecar and exits. **Live** streams annotated
frames into an on-screen window — press **`q`** or **close the window** to quit (`Ctrl-C` also
exits cleanly).

## Defaults differ by mode

`--slice`, `--track`, and `--zoom` are **on in Offline, off in Live** (Live is the leanest:
plain detection boxes, window only, nothing written). An **explicit flag always wins** — so
`--track` turns tracking back on in Live, `--no-slice` turns slicing off in Offline.

`--conf` is **0.15 in both modes** (recall-first). Live has no tracking filter by default, so
the window looks noisy → pass `--conf 0.3` or add `--track`.

## Quick start

```bash
uv sync                                   # one-time setup

# OFFLINE — detect + track everything, write <clip>.annotated.mp4 + <clip>.detections.jsonl
uv run track --source clip.mp4

# LIVE — webcam preview of plain boxes (q to quit)
uv run track --source 0

# LIVE — less noise: filter harder, or turn tracking on
uv run track --source 0 --conf 0.3
uv run track --source 0 --track
```

## Flags

### Source & model
| Flag | Default | Notes |
| --- | --- | --- |
| `--source` | *(required)* | File (Offline) \| camera index \| stream URL (Live) |
| `--weights` | `yolo11n.pt` | Any YOLO `.pt`; custom weights keep all their classes |
| `--device` | `auto` | `auto \| cpu \| mps \| cuda \| cuda:0` |
| `--conf` | `0.15` | Confidence threshold; raise it for a cleaner Live view |
| `--classes` | all | Space-separated COCO ids, e.g. `--classes 0 2` (person, car); `14` = bird |

### Toggles (tri-state: unset → Offline on / Live off; explicit wins)
| Flag | Offline | Live | Turn on / off |
| --- | --- | --- | --- |
| `--slice` / `--no-slice` | on | off | sliced (SAHI) inference for small objects in big frames |
| `--track` / `--no-track` | on | off | in-loop ByteTrack ids + false-positive filter |
| `--zoom` / `--no-zoom` | on | off | picture-in-picture zoom inset |

### Slicing knobs (only matter with `--slice`)
| Flag | Default | Notes |
| --- | --- | --- |
| `--slice-wh W H` | `640 640` | No-op on frames ≤ this size; tiles larger frames |
| `--overlap-ratio W H` | `0.2 0.2` | Slice overlap as a fraction |
| `--overlap-filter` | `nms` | `nms \| nmm` merge strategy |
| `--thread-workers` | `4` | Parallel slice inference workers |

### Zoom & track knobs
| Flag | Default | Notes |
| --- | --- | --- |
| `--zoom-size` | `0.05` | Crop side as a fraction of frame width (smaller = more magnification) |
| `--zoom-max` | `1` | Follow top-N detections by confidence |
| `--zoom-track-id` | — | Pin the inset to one tracker id; **requires `--track`** (so in Live pass `--track` too) |
| `--track-buffer` | `30` | Frames a lost id (and its zoom slot) is held |
| `--track-activation` | `0.25` | Min confidence to start a track |

### Outputs
| Flag | Default | Notes |
| --- | --- | --- |
| `--output` | `<source>.annotated.mp4` | Offline annotated video path |
| `--sidecar` | Offline: derived; Live: off | JSONL detections. **Live rows carry a capture `ts`** (the frame index isn't a clock); Offline schema unchanged |
| `--record` | — | **Live only** — also write an annotated `.mp4` alongside the window (rejected in Offline, which already writes `--output`) |

## Common recipes

```bash
# People + cars only (COCO ids), offline
uv run track --source street.mp4 --classes 0 2

# Birds only — the old default, now explicit
uv run track --source birds.mp4 --classes 14

# Small / low-res clip — slicing usually hurts at ≤640px
uv run track --source clip.mp4 --no-slice

# High-res (1080p/4K) — slicing on (default) with explicit tile size
uv run track --source clip_4k.mp4 --slice --slice-wh 640 640

# Custom weights, GPU
uv run track --source clip.mp4 --weights my_model.pt --device cuda:0

# LIVE with tracking + a persisted record + sidecar
uv run track --source 0 --track --record live.mp4 --sidecar live.jsonl

# LIVE from an RTSP stream, follow one tracked object in the zoom inset
uv run track --source rtsp://cam/stream --track --zoom --zoom-track-id 5
```

## Notes / gotchas

- **Live is noisy by default** because tracking (the FP filter) is off — `--conf 0.3` or
  `--track` fixes it.
- **`--zoom-track-id` needs `--track`.** In Live, `--track` is off by default, so
  `--zoom-track-id 5` alone errors — add `--track`.
- **`--record` is Live-only.** Offline already writes the annotated video via `--output`.
- **Live recordings have no per-frame timestamps** — written at nominal fps, so playback may be
  time-compressed if processing runs slower than real time (see ADR-0010).

Design rationale: `docs/adr/0010-live-mode-camera-stream-ingestion.md` and `CONTEXT.md`.
