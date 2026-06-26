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
  `THICKNESS_SCALE`, `TEXT_SCALE_MULT`, `COLOR_LOOKUP_OVERRIDE`.
- **Zoom styling** — the re-homed `ZOOM_*` aesthetics, plus a new `ZOOM_BORDER_THICKNESS`
  replacing the hardcoded `2` in `zoom.py`.
- **The defaults invariant.** Override-style knobs (`COLOR_LOOKUP_OVERRIDE`, `LABEL_TEXT_COLOR`)
  default to `None` = "don't override, keep current/library behaviour" — critical for
  `LABEL_TEXT_COLOR`, since forcing a fixed colour would defeat supervision's contrast default.
  Value knobs default to today's values (`TRACE_LENGTH=30`, palette `DEFAULT`, scales `1.0`,
  `ZOOM_BORDER_THICKNESS=2`). Adding the theme changes nothing until a constant is edited.

## The annotators factory (the load-bearing decision)

- **`annotators.py` is supervision-only.** `build_box_annotator(frame_wh, color_lookup)`,
  `build_label_annotator(frame_wh)`, `build_trace_annotator(frame_wh)` each read the Appearance
  constants. The no-track path (`pipeline.py`) and the track path (`tracking.py`'s thin
  `_build_track_annotators`, which composes the three into its `_TrackAnnotators` bundle with
  `color_lookup=TRACK`) both call them — so the two paths cannot drift in style.
- **`THICKNESS_SCALE`/`TEXT_SCALE_MULT` are multipliers on the auto-derived values**
  (`calculate_optimal_line_thickness`/`_text_scale`), not absolute overrides, so the
  resolution-adaptive sizing is preserved; at `1.0` the output is byte-identical.
- **Zoom stays cv2/`config`-direct.** `zoom.py` keeps drawing with cv2 and reading the `ZOOM_*`
  constants itself; folding its raster path into the supervision factory would muddy the seam.

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
