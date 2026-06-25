# 03 — Detection step with slicing toggle

Status: ready-for-agent

## Goal

A `detect(frame) -> sv.Detections` function that abstracts over sliced vs whole-frame
inference, so the rest of the pipeline never branches on it (ADR-0002/0003).

## Tasks

- Load `YOLO(--weights)`; resolve `--device` (auto: cuda→mps→cpu; honour override).
- Whole-frame path (`--no-slice`): `model(frame, conf, device)[0]` →
  `sv.Detections.from_ultralytics(...)`.
- Sliced path (`--slice`): `sv.InferenceSlicer(callback=<YOLO-per-slice → sv.Detections>,
  slice_wh=--slice-wh, overlap_ratio_wh=--overlap-ratio,
  overlap_filter=--overlap-filter (default NMS), thread_workers=--thread-workers)`.
- Apply `--conf` (default 0.15, ADR-0004) and `--classes` filter (default bird/14 for
  COCO weights; all classes for custom weights — detect by whether weights are the
  pretrained default).
- Keep these as importable top-level functions (ADR-0001).

## Acceptance

- Both `--slice` and `--no-slice` return `sv.Detections` with identical schema.
- COCO default keeps only birds; `--weights custom.pt` keeps all classes.
- `--conf` and `--classes` overrides take effect.

## Depends on

02.

## Refs

ADR-0001, ADR-0002, ADR-0003, ADR-0004. PRD §CLI surface.
