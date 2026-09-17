"""Device selection: pick the accelerator to run inference on (week 2)."""

from __future__ import annotations


def resolve_device(requested: str | None) -> str:
    """Resolve the torch device string to run the detector on.

    An explicit ``requested`` always wins — the caller asked for it, honour it even if it is
    slower. When ``None``, prefer the best *available* accelerator and fall back to ``"cpu"``.
    On an Apple Silicon Mac that means ``"mps"``; on a CUDA box, ``"cuda"``.
    """
    raise NotImplementedError("Week 2 — see learn/curriculum/week-02-detection.md")
