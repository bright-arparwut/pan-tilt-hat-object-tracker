"""Week 3 acceptance: resolution-relative appearance."""

from __future__ import annotations

import supervision as sv

from object_tracker.annotators import build_detection_annotator, build_label_annotator


def _thickness(annotator):
    for attr in ("thickness", "radius", "base"):
        if hasattr(annotator, attr):
            return getattr(annotator, attr)
    raise AssertionError(f"no size attribute on {type(annotator).__name__}")


def test_thickness_scales_with_frame_size():
    """A 2px outline is right at 640p and invisible at 4K."""
    small = _thickness(build_detection_annotator((640, 480)))
    large = _thickness(build_detection_annotator((3840, 2160)))
    assert large > small


def test_track_lookup_colours_by_identity_not_class():
    annotator = build_label_annotator((640, 480), sv.ColorLookup.TRACK)
    assert annotator.color_lookup == sv.ColorLookup.TRACK
