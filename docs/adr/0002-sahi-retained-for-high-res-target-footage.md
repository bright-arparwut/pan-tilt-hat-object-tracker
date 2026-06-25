# SAHI retained; slice params configurable for high-res target footage

The current test footage is ~384×640, a resolution at which SAHI adds little (a
larger `imgsz` would beat it). We keep SAHI anyway because the *target* footage is
high-resolution (1080p/4K) where sliced inference is the right tool; the small clip
is only for wiring up the loop. Consequently slice size, overlap, and postprocess are
kept configurable rather than tuned to the test clip, so the loop scales to real
footage without code changes.

Slicing is also a runtime *toggle* (`--slice / --no-slice`), not a hard-wired stage.
With slicing off the script runs whole-frame YOLO (`sv.Detections.from_ultralytics`),
which is the correct choice for the small test clip; with it on the script runs
`sv.InferenceSlicer`. Both branches return `sv.Detections`, so annotation, the
Detections Sidecar, the Zoom Inset, and the future tracker are identical regardless of
path. One script therefore serves both the small test footage (`--no-slice`) and real
high-res footage (`--slice`), and the toggle doubles as a free SAHI-vs-plain comparison.
