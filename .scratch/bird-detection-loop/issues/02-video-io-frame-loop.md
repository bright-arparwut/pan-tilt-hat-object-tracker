# 02 — Video I/O and frame loop skeleton

Status: done (implemented in d75e61c on feat/bird-detection-loop)

## Goal

The offline detection loop: open a source video, iterate every frame, write an output
video at matching fps/resolution, with progress and fail-fast error handling.

## Tasks

- `sv.VideoInfo.from_video_path(source)` for fps/resolution; fail fast with a clear
  message if the source can't be opened.
- Iterate with `sv.get_video_frames_generator(source)`; wrap in `tqdm` over frame count.
- Write via `sv.VideoSink(output, video_info)`; `mkdir -p` the output dir.
- Process **every** frame (no skipping — future tracker needs continuity).
- Stub the per-frame hook (detection/annotation lands in 03/04); for now pass frames
  through so the loop is independently runnable.

## Acceptance

- Running on a test clip produces an output video identical in fps/resolution/length.
- Bad `--source` exits non-zero, leaves no partial output file.

## Depends on

01.

## Refs

PRD §Pipeline, §Defaults.
