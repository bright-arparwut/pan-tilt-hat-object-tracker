# object-tracker

Detect and **track any object** in video with a swappable detector backend (**YOLO**
today) and optional **sliced inference** (the SAHI technique, via `supervision`'s
`InferenceSlicer`). Produces an **annotated video** (boxes + `#id` labels + a
picture-in-picture zoom inset) and a **per-frame JSONL detections sidecar**.

Any class, any weights — small flying birds are just one example (`--classes 14`).
Detection is class-agnostic; in-loop `sv.ByteTrack` assigns identities and acts as the
false-positive filter. Design rationale lives in `CONTEXT.md`, `docs/adr/`, and the PRD at
`.scratch/object-tracker-refactor/PRD.md`.

## Setup (uv)

```bash
uv sync
```

## Run

```bash
# Detect + track everything on stock COCO weights (general by default)
uv run track --source clip.mp4

# People + cars (COCO ids 0 and 2)
uv run track --source street.mp4 --classes 0 2

# Birds only — the old default, now explicit (COCO id 14)
uv run track --source birds.mp4 --classes 14

# Small / low-res clip — slicing off is usually better at <=640px frames
uv run track --source clip.mp4 --no-slice

# Real high-res footage (1080p/4K) — slicing on (default)
uv run track --source clip_4k.mp4 --slice --slice-wh 640 640

# Custom-trained weights (all of their classes kept by default)
uv run track --source clip.mp4 --weights my_model.pt
```

Outputs default to `<source>.annotated.mp4` and `<source>.detections.jsonl`.
Run `uv run track --help` for the full flag list.

## Live mode (camera / stream)

The **mode is inferred from `--source`** (ADR-0010): a file path is **Offline**; a camera
index or stream URL is **Live**, streaming annotated frames into an on-screen preview window.

```bash
# Default webcam — a live preview of plain detection boxes (press q or close the window to quit)
uv run track --source 0

# An RTSP / HTTP stream takes the same path
uv run track --source rtsp://camera.local/stream

# Live is noisy without tracking (conf stays 0.15) — filter with a higher --conf …
uv run track --source 0 --conf 0.3

# … or turn tracking back on (off by default in Live)
uv run track --source 0 --track

# Opt in to persistence: a JSONL sidecar (rows carry a capture ts) and/or an annotated recording
uv run track --source 0 --sidecar live.jsonl --record live.mp4
```

Live defaults are the leanest config — slicing, tracking, and the zoom inset are **off**, and
nothing is written unless you pass `--sidecar` / `--record`. Each can be re-enabled explicitly
(`--track`, `--zoom`, `--slice`). Offline defaults are unchanged. See ADR-0010 for the design.

## Notes

- **General by default.** With no `--classes`, all of the weights' classes are kept,
  stock or custom (ADR-0008). Pass `--classes <ids>` to narrow the target.
- **Slicing is a toggle.** Default `--slice-wh 640 640` is a no-op on frames ≤640px and
  tiles automatically on larger frames — same flags scale from test clip to 4K (ADR-0002).
  Slicing is a `SlicedDetector` decorator over any backend, so a future detector gets it
  for free (ADR-0009).
- **Recall-first.** Default `--conf 0.15` intentionally lets noise through; in-loop
  ByteTrack filters it (ADR-0004/0006). A noisy sidecar is by design — confirmed tracks
  carry a `track_id`, dropped noise rows carry `null`.
- **Cost.** High-res + slicing runs tens of forward passes per frame — offline and slow;
  `--thread-workers` and a CUDA GPU help. Correctness is unaffected.
- **Live, not realtime.** Live processes every frame sequentially and does *not* guarantee a
  latency bound — if detection can't keep up, the preview lags or the OS drops frames, and a
  `--record` file (written at nominal fps) may be time-compressed (ADR-0010). The Live sidecar
  frame index counts *received* frames, so each row carries a capture `ts`.
