# Appearance: non-CLI styling as in-code constants in `config.py`

The annotators' look (palette, trace length, label/trace placement, line and text sizing) and
the [Zoom Inset]'s colours were hardcoded inside the `sv.*Annotator(...)` calls in
`pipeline.py`/`tracking.py` and as scattered `ZOOM_*` constants. We give this its own named
category — **Appearance** — as a bannered block of constants in `config.py` (which already
owns resolution-relative constants per ADR-0009), read by a new `annotators.py` factory. It is
deliberately *not* CLI-exposed and *not* an external config file: these are restyle knobs,
edited in source, and **every default reproduces today's output byte-for-byte**.

The load-bearing rename is conceptual: the original ask was a `settings.py`, but "settings" and
"config" are synonyms. The real distinction is **appearance** (how the [Annotated Video] looks)
vs **behaviour** (what the run does, already in `config.py`/the CLI). Naming the category
"Appearance" makes the boundary self-evident; "settings" would have collided with "config".

## What Appearance owns

- **Annotator styling** — `ANNOTATION_PALETTE`, `TRACE_LENGTH` (previously the silent
  supervision default of 30), `LABEL_TEXT_COLOR`, `LABEL_POSITION`, `TRACE_POSITION`,
  `THICKNESS_SCALE`, `TEXT_SCALE_MULT`, `COLOR_LOOKUP_OVERRIDE`, `DETECTION_STYLE` (selectable
  per-Detection style — see "Detection style" below).
- **Zoom styling** — the re-homed `ZOOM_*` aesthetics, plus a new `ZOOM_BORDER_THICKNESS`
  replacing the hardcoded `2` in `zoom.py`.
- **The defaults invariant.** Override-style knobs (`COLOR_LOOKUP_OVERRIDE`, `LABEL_TEXT_COLOR`)
  default to `None` = "don't override, keep current/library behaviour" — critical for
  `LABEL_TEXT_COLOR`, since forcing a fixed colour would defeat supervision's contrast default.
  Value knobs default to today's values (`TRACE_LENGTH=30`, palette `DEFAULT`, scales `1.0`,
  `ZOOM_BORDER_THICKNESS=2`). Adding the theme changes nothing until a constant is edited.

## The annotators factory (the load-bearing decision)

- **`annotators.py` is supervision-only.** `build_detection_annotator(frame_wh, color_lookup)`,
  `build_label_annotator(frame_wh)`, `build_trace_annotator(frame_wh)` each read the Appearance
  constants. The no-track path (`pipeline.py`) and the track path (`tracking.py`'s thin
  `_build_track_annotators`, which composes the three into its `_TrackAnnotators` bundle with
  `color_lookup=TRACK`) both call them — so the two paths cannot drift in style.
- **`THICKNESS_SCALE`/`TEXT_SCALE_MULT` are multipliers on the auto-derived values**
  (`calculate_optimal_line_thickness`/`_text_scale`), not absolute overrides, so the
  resolution-adaptive sizing is preserved; at `1.0` the output is byte-identical.
- **Zoom stays cv2/`config`-direct.** `zoom.py` keeps drawing with cv2 and reading the `ZOOM_*`
  constants itself; folding its raster path into the supervision factory would muddy the seam.

## Detection style (added)

`DETECTION_STYLE` selects how each [Detection] is drawn — a `DetectionStyle` enum (`config.py`,
beside the default) mapped to a supervision annotator by `annotators.py`'s `_DETECTION_STYLES`.
Same *shape* of decision as the rest of Appearance: an in-code constant, not a CLI flag, shared
by both modes, default (`BOX` → `sv.BoxAnnotator`) reproducing today's output byte-for-byte.

This started narrower — five thickness-uniform box *shapes* sharing one constructor — and was
then widened to fills, markers and pixel-effects, which forced the constructor decision below.

- **Per-style builders, not one uniform constructor.** The ten styles split into three
  constructor groups: outlines (`BOX`, `ROUND`, `CORNER`, `CIRCLE`, `ELLIPSE`) take
  `(color, thickness, color_lookup)`; fills/markers (`COLOR`, `DOT`, `TRIANGLE`) take
  `(color, color_lookup)` only; effects (`BLUR`, `PIXELATE`) take no colour at all. Because they
  do not share a contract, `_DETECTION_STYLES` maps each style to its own builder
  (`_outline`/`_filled`/`_effect`) instead of a single `cls(color=…, thickness=…)` call. Extras
  (`opacity`, `radius`, `roundness`, kernel/pixel size) ride supervision's defaults — no new
  Appearance constants (YAGNI).
- **`BLUR`/`PIXELATE` ignore the palette and `color_lookup`** — they anonymise the box region
  rather than colour it. Their builders pass no colour args; in the track path the `#id` label
  still renders on top, so an anonymised object stays identifiable by id.
- **Mask-based styles are excluded by necessity** — `Mask`/`Polygon`/`Halo` need a segmentation
  mask the [Detector] does not emit (it produces boxes, not masks); `HaloAnnotator` in
  particular is a *silent no-op* on mask-less detections — it draws nothing, raises nothing — so
  offering it would be a trap. `HeatMap` (stateful cross-frame aggregate) and `PercentageBar`
  (a confidence meter, not a per-object mark) are out for being a different shape of thing.
- **The widened type is a public-API union** — `DetectionAnn = sv.BoxAnnotator |
  sv.RoundBoxAnnotator | … | sv.PixelateAnnotator` (ten members), declared next to
  `_DETECTION_STYLES` so the two stay in sync by proximity. Preferred over reaching into the
  non-public `supervision.annotators.base.BaseAnnotator`.

## Considered options

- **A separate `settings.py`** — rejected: "settings" and "config" are synonyms, so two files
  force a "which file does this knob live in?" guess forever with no principled line, and
  `config.py` is ~70 lines with no size pressure. `config.py` already holds these constants.
- **An external config format (TOML/YAML/env)** — rejected: YAGNI. There is no per-deployment
  styling need, and it would add a parse/validate boundary for values a developer edits in
  source anyway.
- **A frozen `StyleConfig` dataclass threaded through `run()`** — rejected: appearance does not
  vary per run and is not CLI-driven, so a dataclass is ceremony you instantiate once and never
  vary. Module constants are the honest shape.
- **Wiring the constants inline at both call sites** — rejected: it duplicates the
  palette/scale/lookup logic across the two box-annotator builds, inviting the no-track and
  track views to drift apart.

## Consequences

- **Two colour conventions coexist, by necessity.** cv2/zoom drawing uses **BGR tuples**
  (`ZOOM_BORDER_BGR`, `ZOOM_BORDER_THICKNESS`); supervision annotators use **`sv.Color` /
  `sv.ColorPalette`** (`ANNOTATION_PALETTE`, `LABEL_TEXT_COLOR`). They cannot unify — the two
  libraries want different types — so the Appearance block is bannered into two sub-groups.
- **No validation layer.** These are developer-edited source constants, not a runtime boundary;
  a bad value fails visibly via supervision/cv2 rather than through an added check.
- **`config.py` now spans three concerns** — CLI defaults, Appearance, and the run-config
  dataclasses. The in-file banner is what marks the Appearance line, since there is
  intentionally no filename boundary.
