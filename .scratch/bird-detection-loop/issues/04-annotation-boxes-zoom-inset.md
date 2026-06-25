# 04 — Annotation: boxes + picture-in-picture zoom inset

Status: done (implemented in d75e61c on feat/bird-detection-loop; zoom-size default corrected 0.15 → 0.05)

Superseded in part by issue 07 (multi-bird zoom): the inset now follows the top-N
detections via `--zoom-max` (default 1 = this single-inset behaviour), and empty frames
draw no strip — no hold-last (see ADR-0005). Points changed below are annotated inline.

## Goal

Render detections legibly on each frame: thin boxes plus a PiP Zoom Inset that follows
the top-confidence bird (so ~5px birds are visible).

## Tasks

- `sv.BoxAnnotator`, no labels (labels dwarf tiny boxes). **Box thickness must be
  resolution-relative** — derive from `sv.calculate_optimal_line_thickness(
  resolution_wh=video_info.resolution_wh)`, not a hard-coded 1px (a 1px box is
  invisible on 4K).
- Zoom Inset (`--zoom`, default on):
  - Pick the highest-confidence detection each frame; take its centre.
  - EMA-smooth the centre (configurable alpha) so the inset doesn't teleport.
  - **Crop size resolution-relative**: a fraction of frame (`--zoom-size`, default 0.05
    of frame width) rather than a fixed pixel box, so zoom strength is consistent across
    384×640, 1080p, and 4K. Panel is a fixed fraction of frame (1/4), so effective
    magnification = 0.25 / zoom-size (≈5× at defaults). NOTE: a too-large crop defeats
    the inset — verified a 0.15 default gave only ~1.7× and hid the bird; 0.05 → ~5×.
  - No detections → no inset (or last-known, decide and document); frame still written.
    [07 resolved: no strip, no hold-last — WYSIWYG (ADR-0005).]
- Single region only — documented limitation (CONTEXT: Zoom Inset).
  [07 superseded: up to N regions via `--zoom-max`; N=1 keeps this behaviour.]
- Known behaviour: the inset follows `argmax(confidence)`. When every detection is
  near-threshold noise (recall-first, ADR-0004), the top pick teleports and the EMA
  centre drifts to empty background; with a genuine high-confidence bird it tracks
  smoothly. Acceptable — the inset is a viewing aid, not a guarantee.

## Resolution behaviour

All rendering must look right across resolutions (the loop targets high-res footage —
ADR-0002). No fixed-pixel rendering constants: box thickness and zoom crop/panel sizes
derive from `video_info.resolution_wh`.

## Acceptance

- Tiny birds are visibly magnified in the inset; inset tracks motion smoothly.
- `--no-zoom` produces boxes only.

## Depends on

03.

## Refs

CONTEXT.md (Zoom Inset). PRD §Outputs.
