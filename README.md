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
