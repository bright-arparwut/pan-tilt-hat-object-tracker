from __future__ import annotations

from turret_pi.teleop import STEP_DEG, key_to_delta


def test_wasd_map_to_signed_nudges():
    assert key_to_delta("d") == (STEP_DEG, 0.0)    # right -> +pan
    assert key_to_delta("a") == (-STEP_DEG, 0.0)   # left  -> -pan
    assert key_to_delta("w") == (0.0, STEP_DEG)    # up    -> +tilt
    assert key_to_delta("s") == (0.0, -STEP_DEG)   # down  -> -tilt


def test_key_is_case_insensitive():
    assert key_to_delta("D") == (STEP_DEG, 0.0)


def test_unknown_key_is_a_no_move():
    assert key_to_delta("x") == (0.0, 0.0)


def test_step_size_is_configurable():
    assert key_to_delta("d", step_deg=2.0) == (2.0, 0.0)
