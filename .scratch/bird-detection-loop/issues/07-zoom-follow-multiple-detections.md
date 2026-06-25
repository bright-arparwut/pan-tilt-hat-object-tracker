# 07 — Zoom Inset: follow up to N detections (`--zoom-max`)

Status: ready-for-agent

## Goal

Let the Zoom Inset follow more than one bird. Today it shows a single panel on the
top-confidence Detection (issue 04). Generalise it to a vertical strip of up to N
**Zoom Panels** — the top-N Detections by confidence — with N configurable from the CLI.
At `N=1` the behaviour is the current single inset (with one deliberate exception, below).

## Decisions (from grilling session)

- **Visual form** — one Zoom Panel per followed Detection (not a union-bbox crop, not a
  centroid crop). See CONTEXT.md (Zoom Panel, Zoom Inset).
- **Count cap** — top-N by confidence. Recall-first (ADR-0004) means a frame can carry
  many near-threshold Detections; ranking by confidence keeps the strip bounded and
  biased toward real birds.
- **CLI** — `--zoom`/`--no-zoom` stays the master on/off. Add `--zoom-max N` (int,
  **default 1**). The feature is purely additive: nothing changes unless the user asks.
- **Layout** — vertical strip down the **right edge**, stacked top→bottom. Panel side =
  `min(0.25·fw, fh / N)`. At `N=1` this equals today's top-right quarter-frame panel.
- **Slot order / stability** — slots are **confidence-ordered** (slot 0 = highest). Only
  slot-0's centre is EMA-smoothed (preserving today's no-teleport behaviour); slots 1+
  redraw fresh each frame. Panels below slot 0 may reorder/flicker as confidences cross
  — **accepted**: the inset is a viewing aid, not a guarantee (issue 04).
- **No cross-frame association** — panels are NOT matched to the previous frame
  (no nearest-neighbour / IoU). Associating the same bird across frames is the future
  tracker's job (ADR-0001); doing it here would pre-empt and duplicate ByteTrack.
- **Sparse frames (WYSIWYG)** — draw exactly the current frame's Detections: fewer than
  N Detections → fewer panels; **zero Detections → no strip at all; no hold-last.**
  This drops today's empty-frame persistence (see "Supersedes" below) and, as a bonus,
  removes the issue-04 artifact where the EMA centre drifts onto empty background on
  noise-only frames.
- **Magnification** — one shared `--zoom-size`. Magnification = `panel / (zoom_size·fw)`,
  so panels magnify less as N grows (e.g. 1080p: ~5× at N=1, ~1.9× at N=6). Documented,
  not auto-corrected — the user lowers `--zoom-size` to compensate when following a flock.

## Tasks

- CLI (`build_parser`): add `--zoom-max` (`type=int`, `default=1`). Leave `--zoom` /
  `--no-zoom` and `--zoom-size` as-is.
- Validation (`main`): require `--zoom-max >= 1`; exit non-zero with a clear message
  otherwise (mirror the existing `--zoom-size` check).
- Replace `_top_center` with a top-N selector returning the centres of the N
  highest-confidence Detections (confidence-descending). Empty Detections → empty list.
- Generalise `draw_zoom_inset` → draw a right-edge strip of up to N panels:
  - panel side = `min(int(ZOOM_PANEL_FRACTION·fw), fh // max(1, N))`;
  - panel k occupies `y = k·panel … (k+1)·panel`, `x = fw-panel … fw`;
  - each panel = `--zoom-size` crop around its centre, resized to the panel, green border
    (`ZOOM_BORDER_BGR`), same crop/clamp math as today.
- Smoothing: keep EMA on slot-0's centre only (carry `zoom_center` for slot 0 across
  frames *when a Detection exists*; on an empty frame draw nothing and reset slot-0 EMA
  so a reappearing bird snaps rather than sweeping from a stale point).
- `run()`: thread `zoom_max` through; build the per-frame panel-centre list; call the
  generalised drawer.

## Resolution behaviour

Unchanged contract from issue 04 / ADR-0002: no fixed-pixel constants. Panel and crop
sizes derive from `video_info.resolution_wh`; the strip looks right on 384×640, 1080p,
and 4K. `ZOOM_PANEL_FRACTION` (0.25) and `--zoom-size` remain the only tunables.

## Acceptance

1. `--zoom-max 1` (default): single top-right panel on the top-confidence Detection,
   EMA-smoothed — visually today's inset on frames that have a Detection.
2. `--zoom-max 4`: up to 4 panels stack down the right edge, confidence-ordered; with
   fewer than 4 Detections, fewer panels draw.
3. Empty frame (no Detections): no strip is drawn; the frame is still written.
4. `--no-zoom`: no panels regardless of `--zoom-max`.
5. `--zoom-max 0` (or negative): exits non-zero with a clear message; no partial output.
6. Sidecar output is byte-for-byte unaffected by any zoom flag (rendering-only feature).

## Supersedes / note for doc sync (not done in this issue)

- **PRD acceptance #5** ("zoom inset follows *the* top-confidence detection") — now
  "follows the top-N by confidence (N=`--zoom-max`, default 1)".
- **PRD CLI table** — add a `--zoom-max` row (default `1`).
- **Issue 04** open item "No detections → no inset (or last-known, decide and document)"
  — resolved as **no strip, no hold-last** (WYSIWYG); today's hold-last is dropped.

## Depends on

04 (boxes + single zoom inset).

## Refs

CONTEXT.md (Zoom Panel, Zoom Inset). ADR-0001 (no in-loop tracking/association),
ADR-0004 (recall-first → bounded by top-N). PRD §Outputs, §CLI surface. Issue 04.
