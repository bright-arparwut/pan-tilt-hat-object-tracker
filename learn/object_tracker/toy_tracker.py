"""A hand-rolled multi-object tracker — IoU + greedy assignment (week 5, SANDBOX ONLY).

This module does **not** exist in the reference implementation. It exists so that you write
a tracker before you use one, and so that in week 6 you can measure exactly what ByteTrack
buys you over the obvious approach.

The whole of tracking is one question: frame *t* had N boxes, frame *t+1* has M boxes —
which is which? Everything else (Kalman filters, re-identification embeddings, ByteTrack's
second association pass) is a better answer to that same question.

You throw this away in week 6. That is fine. It will have done its job.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import supervision as sv

DEFAULT_IOU_THRESHOLD = 0.3
DEFAULT_MAX_AGE = 30  # frames an unmatched track survives before it is deleted


def iou_matrix(boxes_a: np.ndarray, boxes_b: np.ndarray) -> np.ndarray:
    """Pairwise IoU between two sets of ``xyxy`` boxes → shape ``(len(a), len(b))``.

    Intersection over union: the area both boxes share, divided by the area they jointly
    cover. 1.0 for identical boxes, 0.0 for disjoint ones.

    You met this formula in week 2 as NMS's *suppression* metric. Here it is the *matching*
    metric — same arithmetic, opposite purpose.

    Vectorise it (no Python loop over pairs). Watch the degenerate cases: zero-area boxes,
    and a union of zero.
    """
    raise NotImplementedError("Week 5 — see learn/curriculum/week-05-tracking-by-hand.md")


@dataclass(frozen=True)
class Track:
    """One tracked identity: its id, its last known box, and when it was last matched."""

    track_id: int
    xyxy: tuple[float, float, float, float]
    last_seen_frame: int


@dataclass(frozen=True)
class ToyTrackerState:
    """Immutable tracker state, threaded through ``update`` (the project's house style)."""

    tracks: tuple[Track, ...] = ()
    next_id: int = 1


def match_greedy(
    iou: np.ndarray, threshold: float = DEFAULT_IOU_THRESHOLD
) -> list[tuple[int, int]]:
    """Greedy assignment: repeatedly take the highest-IoU pair above ``threshold``, remove
    both from consideration, repeat. Returns ``[(track_index, detection_index), ...]``.

    Greedy is not optimal. The Hungarian algorithm minimises *total* cost instead of taking
    the locally best pair each time. Before you move on, construct by hand a 2x2 IoU matrix
    where greedy picks the pair that forces a worse overall assignment — and write it down as
    a test. Knowing your algorithm's failure mode is the point of building it.
    """
    raise NotImplementedError("Week 5 — see learn/curriculum/week-05-tracking-by-hand.md")


def update(
    state: ToyTrackerState,
    detections: sv.Detections,
    frame_idx: int,
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
    max_age: int = DEFAULT_MAX_AGE,
) -> tuple[sv.Detections, ToyTrackerState]:
    """Advance one frame: match, birth, age, die. Returns detections carrying ``tracker_id``.

    1. **Match** existing tracks against this frame's detections by IoU.
    2. **Update** each matched track's box and ``last_seen_frame``.
    3. **Birth** a new track (fresh id) for every unmatched detection.
    4. **Age out** any track unseen for more than ``max_age`` frames.

    Do *not* kill a track on its first miss — a detector blinks, and an object briefly behind
    a lamp post is still the same object. That patience window is the single cheapest
    robustness win in tracking.

    Ids are never reused once retired: a revived id would silently merge two objects'
    histories.
    """
    raise NotImplementedError("Week 5 — see learn/curriculum/week-05-tracking-by-hand.md")
