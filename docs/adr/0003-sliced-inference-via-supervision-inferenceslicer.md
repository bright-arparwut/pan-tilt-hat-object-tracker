# Sliced inference via supervision InferenceSlicer, not the obss/sahi package

We implement the SAHI technique with `supervision`'s `sv.InferenceSlicer` rather than
the `sahi` (obss/sahi) package the project goal names. Rationale: single ecosystem.
`InferenceSlicer` returns `sv.Detections`, which flow directly into supervision's
annotators, `sv.VideoSink` (the saved video), and later `sv.ByteTrack` — and
`sv.ByteTrack` is decoupled from Ultralytics, so it consumes sliced detections that
the native `model.track()` cannot (see ADR-0001). This keeps the single-script build
on one computer-vision toolkit.

Trade-off: we forgo `sahi`'s `IOS` match metric and its optional full-frame pass
(`perform_standard_pred`). If recall on birds straddling tile boundaries proves
insufficient on real high-res footage, the first lever is `overlap_filter =
NON_MAX_MERGE`; only if that is inadequate do we revisit the obss/sahi package.

So "SAHI" in this repo means the *technique*, implemented via supervision — not the
`sahi` PyPI package.
