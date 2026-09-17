"""Detections sidecar: serialise per-frame detections to plain dicts (ADR-0001)."""

from __future__ import annotations

import supervision as sv


def frame_record(idx: int, records: list[dict], ts: float | None = None) -> dict:
    """Wrap one frame's detection records into the JSONL object the sidecar writes.

    Offline (``ts=None``) is ``{"frame", "detections"}``. Live passes a capture ``ts`` (epoch
    seconds) — inserted **between** ``frame`` and ``detections`` — because on a Live Source
    the frame index counts *received* frames, not wall-clock time (ADR-0010 §Throughput).

    Key order is part of the contract: a downstream consumer diffing sidecars across runs
    should see no spurious change. Build the dict in the documented order.
    """
    raise NotImplementedError("Week 3 — see learn/curriculum/week-03-annotation-sidecar.md")


def detection_records(
    detections: sv.Detections, with_track_id: bool = False
) -> list[dict]:
    """Serialise detections to plain dicts (source-pixel xyxy).

    One dict per detection: ``xyxy`` (4 floats, rounded to 1 decimal — sub-pixel precision is
    noise), ``conf`` (rounded to 4), ``cls`` (int), ``name`` (str from
    ``detections.data["class_name"]`` when present).

    When ``with_track_id`` (``--track``, week 6), each row gains ``"track_id"`` read from
    ``detections.tracker_id``, or ``null`` when the frame carries no ids. When ``False``
    the key is **omitted entirely** — not set to null — so the ``--no-track`` schema stays
    exactly what it was before tracking existed.

    Every numeric field must be a plain Python ``int``/``float``: ``xyxy`` is numpy float32
    and ``json.dumps`` cannot serialise that.
    """
    raise NotImplementedError("Week 3 — see learn/curriculum/week-03-annotation-sidecar.md")
