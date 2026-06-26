"""Device resolution: pick the inference device for a run."""

from __future__ import annotations


def resolve_device(requested: str | None) -> str:
    """Pick cuda -> mps -> cpu unless the user forced a device."""
    if requested and requested != "auto":
        return requested
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"
