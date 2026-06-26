"""Run configuration: defaults/constants and the frozen per-run config dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# --- defaults / constants (resolution-relative where it matters) -------------------
COCO_BIRD_CLASS_ID = 14  # COCO id for "bird" — the canonical example class (--classes 14)
DEFAULT_WEIGHTS = "yolo11n.pt"
DEFAULT_CONF = 0.15  # recall-first; tracking is the false-positive filter (ADR-0004)
DEFAULT_SLICE_WH = (640, 640)
DEFAULT_OVERLAP_RATIO = (0.2, 0.2)
DEFAULT_THREAD_WORKERS = 4
DEFAULT_TRACK_BUFFER = 30  # lost_track_buffer: frames a lost id is held (ADR-0006)
DEFAULT_TRACK_ACTIVATION = 0.25  # min conf to start a track; sits above recall-first conf
DEFAULT_ZOOM_SIZE = 0.05  # crop side as a fraction of frame width
ZOOM_PANEL_FRACTION = 0.25  # inset panel side as a fraction of frame width
# effective magnification = ZOOM_PANEL_FRACTION / zoom_size (≈5x at defaults)
ZOOM_EMA_ALPHA = 0.3  # smoothing on the inset centre (lower = smoother)
ZOOM_BORDER_BGR = (0, 255, 0)
ZOOM_MIN_CROP_PX = 8  # floor on the crop side so tiny --zoom-size stays sampleable
ZOOM_LABEL_SCALE = 0.006  # identity-slot #id font scale per panel px (resolution-relative)
ZOOM_LABEL_MIN_SCALE = 0.4


@dataclass(frozen=True)
class DetectConfig:
    """Everything the per-frame detector needs, fixed for a run."""

    weights: str
    conf: float
    classes: tuple[int, ...] | None  # None = keep all classes
    device: str
    use_slicing: bool
    slice_wh: tuple[int, int]
    overlap_ratio_wh: tuple[float, float]
    overlap_filter: str  # "nms" | "nmm"
    thread_workers: int


@dataclass(frozen=True)
class RunPaths:
    source: Path
    output: Path
    sidecar: Path


@dataclass(frozen=True)
class TrackConfig:
    """In-loop ByteTrack settings for a run (ADR-0006)."""

    enabled: bool
    activation: float  # track_activation_threshold (min conf to start a track)
    buffer: int  # lost_track_buffer (frames a lost id and its zoom slot are held)


@dataclass(frozen=True)
class ZoomConfig:
    """Zoom Inset settings for a run (see CONTEXT.md: Zoom Inset / Zoom Panel)."""

    enabled: bool
    size: float  # crop side as a fraction of frame width
    max_panels: int  # confidence-mode: follow top-N; identity-mode: id-pinned slot count
    track_id: int | None = None  # identity-mode: lock the inset to one tracker_id
