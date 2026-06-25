# yolo-byteTrack-sot

Detect small flying birds in video with **YOLO + sliced inference** (the SAHI
technique, via `supervision`'s `InferenceSlicer`), saving an **annotated video**
(boxes + a picture-in-picture zoom inset) and a **per-frame JSONL detections sidecar**.

The sidecar is the tracker-ready handoff for a future ByteTrack / single-object-tracking
stage. Design rationale lives in `CONTEXT.md`, `docs/adr/`, and the PRD at
`.scratch/bird-detection-loop/PRD.md`.

## Setup (uv)

```bash
uv sync
```

## Run

```bash
# Small / low-res clip — slicing off is usually better at <=640px frames
uv run detect-birds --source clip.mp4 --no-slice

# Real high-res footage (1080p/4K) — slicing on (default)
uv run detect-birds --source clip_4k.mp4 --slice --slice-wh 640 640

# Custom weights keep all classes; pretrained default keeps only birds (COCO id 14)
uv run detect-birds --source clip.mp4 --weights my_birds.pt
```

Outputs default to `<source>.annotated.mp4` and `<source>.detections.jsonl`.
Run `uv run detect-birds --help` for the full flag list.

## Notes

- **Slicing is a toggle.** Default `--slice-wh 640 640` is a no-op on frames ≤640px and
  tiles automatically on larger frames — same flags scale from test clip to 4K (ADR-0002).
- **Recall-first.** Default `--conf 0.15` intentionally lets noise through; the future
  tracker filters it (ADR-0004). A noisy sidecar is by design.
- **Cost.** High-res + slicing runs tens of forward passes per frame — offline and slow;
  `--thread-workers` and a CUDA GPU help. Correctness is unaffected.
