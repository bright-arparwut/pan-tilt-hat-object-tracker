"""Run configuration: defaults/constants and the frozen per-run config dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import supervision as sv


class DetectionStyle(Enum):
    """The selectable per-Detection visual style (Appearance / ADR-0011), built into a
    supervision annotator by ``annotators.py``. ``BOX`` reproduces the prior output. The
    members span box outlines, fills, markers and pixel effects — they do *not* share a
    constructor, so the factory builds each one its own way (see ``_DETECTION_STYLES``).
    """

    BOX = "box"  # sv.BoxAnnotator — the default rectangle outline
    ROUND = "round"  # sv.RoundBoxAnnotator — rounded rectangle
    CORNER = "corner"  # sv.BoxCornerAnnotator — corner brackets
    CIRCLE = "circle"  # sv.CircleAnnotator — enclosing circle
    ELLIPSE = "ellipse"  # sv.EllipseAnnotator — bottom ellipse
    COLOR = "color"  # sv.ColorAnnotator — translucent box fill
    DOT = "dot"  # sv.DotAnnotator — marker dot
    TRIANGLE = "triangle"  # sv.TriangleAnnotator — marker above the box
    BLUR = "blur"  # sv.BlurAnnotator — anonymise the box region (no colour)
    PIXELATE = "pixelate"  # sv.PixelateAnnotator — anonymise the box region (no colour)


class TrackerKind(Enum):
    """The selectable multi-object Tracker (ADR-0012), passed to Ultralytics
    ``model.track()`` as its ``tracker`` argument. Each value is the shipped tracker config
    filename; ``BYTETRACK`` is the default and reproduces the prior in-loop ByteTrack.
    """

    BYTETRACK = "bytetrack.yaml"
    BOTSORT = "botsort.yaml"
    OCSORT = "ocsort.yaml"
    DEEPOCSORT = "deepocsort.yaml"
    FASTTRACKER = "fasttracker.yaml"
    TRACKTRACK = "tracktrack.yaml"


# --- defaults / constants (resolution-relative where it matters) -------------------
COCO_BIRD_CLASS_ID = (
    14  # COCO id for "bird" — the canonical example class (--classes 14)
)
DEFAULT_WEIGHTS = "yolo11x.pt"
DEFAULT_CONF = 0.15  # recall-first; tracking is the false-positive filter (ADR-0004)
DEFAULT_SLICE_WH = (640, 640)
DEFAULT_OVERLAP_RATIO = (0.2, 0.2)
DEFAULT_THREAD_WORKERS = 4
# Guardrail (not a hard limit): below this absolute tile side (px), slices are upscaled so
# hard that small objects vanish and objects larger than a tile fragment into overlapping
# boxes. Slicing targets large/4K frames (ADR-0002), so legitimate tiles are >= this; the CLI
# warns when --slice-wh falls under it. See detection.slice_warnings.
MIN_SLICE_PX = 128
# Zoom-slot hold: frames a lost id's Zoom Slot is held black. Mirrors the tracker yaml's
# track_buffer (bytetrack ships 30) so the slot persists exactly as long as the id can
# revive (ADR-0007/0012). No longer reaches the tracker — model.track() owns its thresholds.
DEFAULT_TRACK_BUFFER = 60
# Live cameras/streams sometimes report fps=0 (CAP_PROP_FPS). We need a positive nominal
# value because it feeds annotator scaling (frame-count based), so fall back to this when
# the device doesn't report one (ADR-0010 §Consequences).
DEFAULT_CAMERA_FPS = 30
DEFAULT_TRACKER = (
    TrackerKind.BYTETRACK
)  # default Tracker (ADR-0012); preserves ADR-0006
DEFAULT_ZOOM_SIZE = 0.05  # crop side as a fraction of frame width

# --- turret (ADR-0013) — Aim Controller defaults; deliberately gentle, tune on hardware ---
DEFAULT_TURRET_KP = 0.05  # deg per px error
DEFAULT_TURRET_KI = 0.0  # Phase 3 is P-only; Phase 4 turns this on
DEFAULT_TURRET_KD = 0.0  # ditto
DEFAULT_TURRET_DEADZONE_PX = (
    6.0  # |error| below this is treated as zero (kills at-rest jitter)
)
DEFAULT_TURRET_MAX_DELTA_DEG = 5.0  # per-step slew clamp on a single Aim Command
DEFAULT_TURRET_PORT = 9000

# --- sentry mode (2026-07-22 design) — no-target pan sweep for the Actuator Sink -----
SENTRY_GRACE_S = 2.0  # unlocked time before the sweep starts
SENTRY_SPEED_DEG_S = 15.0  # continuous sweep speed (pan sweep AND tilt relocation)
SENTRY_PAN_MIN_DEG = (
    0.0  # mirrors turret/turret_pi/servo.py PAN_MIN_DEG (no shared module)
)
SENTRY_PAN_MAX_DEG = 180.0  # mirrors turret/turret_pi/servo.py PAN_MAX_DEG
SENTRY_TILT_MIN_DEG = 20.0  # mirrors turret/turret_pi/servo.py TILT_MIN_DEG
SENTRY_TILT_MAX_DEG = 115.0  # mirrors turret/turret_pi/servo.py TILT_MAX_DEG
SENTRY_TILT_DEFAULT_DEG = 90.0  # patrol tilt the no-target sweep relocates to and holds

# --- appearance (non-CLI styling; defaults reproduce prior output — ADR-0011) -------
# The look of the Annotated Video, edited here rather than via --flags. Two colour
# conventions coexist: supervision annotators take sv.Color / sv.ColorPalette; the cv2
# zoom raster takes BGR tuples. They can't unify (different libraries), so they're grouped.
#
# supervision annotators (sv.* types) — fed to the annotators.py factory:
DETECTION_STYLE = (
    DetectionStyle.BOX
)  # per-Detection style; BOX = prior look (annotators._DETECTION_STYLES)
ANNOTATION_PALETTE = sv.ColorPalette.DEFAULT  # box/label/trace colours (both modes)
TRACE_LENGTH = 30  # sv.TraceAnnotator trace_length: trail length in frames
LABEL_TEXT_COLOR: sv.Color | None = (
    None  # None -> keep sv default; an sv.Color forces it
)
LABEL_POSITION = sv.Position.TOP_CENTER  # sv.LabelAnnotator text_position
TRACE_POSITION = sv.Position.CENTER  # sv.TraceAnnotator anchor
THICKNESS_SCALE = (
    0.5  # multiplier on calculate_optimal_line_thickness (1.0 = unchanged)
)
TEXT_SCALE_MULT = 0.5  # multiplier on calculate_optimal_text_scale (1.0 = unchanged)
# None -> mode-aware lookup (CLASS no-track / TRACK track); an sv.ColorLookup forces both.
COLOR_LOOKUP_OVERRIDE: sv.ColorLookup | None = None
#
# cv2 zoom raster (BGR tuples) — read directly by zoom.py:
ZOOM_PANEL_FRACTION = 0.25  # inset panel side as a fraction of frame width
# effective magnification = ZOOM_PANEL_FRACTION / zoom_size (≈5x at defaults)
ZOOM_EMA_ALPHA = 0.3  # smoothing on the inset centre (lower = smoother)
ZOOM_BORDER_BGR = (0, 255, 0)
ZOOM_BORDER_THICKNESS = 2  # cv2 border line width on each zoom panel
ZOOM_MIN_CROP_PX = 8  # floor on the crop side so tiny --zoom-size stays sampleable
ZOOM_LABEL_SCALE = (
    0.006  # identity-slot #id font scale per panel px (resolution-relative)
)
ZOOM_LABEL_MIN_SCALE = 0.4


# --- run configs (YOU IMPLEMENT) ---------------------------------------------------
# The fields are gone; the docstrings say what each config is for. Add the fields in the
# week that needs them — the week doc lists exactly which. Keep them `frozen=True`:
# a run config that can be mutated mid-run is a bug waiting to happen.


@dataclass(frozen=True)
class DetectConfig:
    """Everything the per-frame detector needs, fixed for a run.

    Week 1: weights, conf, classes, device.
    Week 4: use_slicing, slice_wh, overlap_ratio_wh, overlap_filter, thread_workers.
    """

    # TODO(week-01, week-04)


@dataclass(frozen=True)
class RunPaths:
    """The three paths a run reads from and writes to (week 1)."""

    # TODO(week-01): source, output, sidecar


@dataclass(frozen=True)
class TrackConfig:
    """Tracking settings for a run (ADR-0012): which Tracker, and the Zoom Slot hold.

    Week 6: enabled, tracker. Week 7: buffer.
    """

    # TODO(week-06, week-07)


@dataclass(frozen=True)
class ZoomConfig:
    """Zoom Inset settings for a run (see CONTEXT.md: Zoom Inset / Zoom Panel).

    Week 1: enabled, size, max_panels. Week 7: track_id.
    """

    # TODO(week-01, week-07)


@dataclass(frozen=True)
class AimGains:
    """Aim Controller gains (ADR-0013): P-only when ``ki == kd == 0.0``; the same
    ``aim_controller.step`` becomes PID purely by which gains are nonzero (week 11).
    """

    # TODO(week-11): kp, ki, kd, deadzone_px, max_delta_deg


@dataclass(frozen=True)
class SentryConfig:
    """Sentry-mode tuning (ADR-0014): grace, sweep speed, and the host-side mirrors of the
    Pi's servo clamps. ``max_delta_deg`` reuses the turret's per-step slew clamp so a
    pipeline stall can't produce a violent sweep jump (week 12).
    """

    # TODO(week-12): grace_s, speed_deg_s, pan/tilt min+max, tilt_default_deg, max_delta_deg


@dataclass(frozen=True)
class TurretConfig:
    """Turret Actuator Sink settings for a run (ADR-0013): where Aim Commands are sent."""

    # TODO(week-11): host, port, gains
