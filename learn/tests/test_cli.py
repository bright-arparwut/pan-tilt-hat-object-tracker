"""Week 8 acceptance: tri-state toggles and arg validation (pure, no parser needed)."""

from __future__ import annotations

import pytest

from object_tracker.cli import resolve_toggle, validation_error


@pytest.mark.parametrize(
    "value, is_live, expected",
    [
        (None, False, True),    # unset, Offline -> on
        (None, True, False),    # unset, Live    -> off (the leanest live config)
        (True, True, True),     # an explicit flag always wins
        (False, False, False),
    ],
)
def test_resolve_toggle_defaults_on_offline_and_off_live(value, is_live, expected):
    assert resolve_toggle(value, is_live) is expected


def test_validation_rejects_a_zoom_size_outside_the_unit_interval():
    assert validation_error(0.0, 1) is not None
    assert validation_error(1.5, 1) is not None
    assert validation_error(0.05, 1) is None


def test_validation_rejects_identity_features_without_tracking():
    assert validation_error(0.05, 1, track=False, zoom_track_id=7) is not None
    assert validation_error(0.05, 1, track=False, turret=True) is not None
