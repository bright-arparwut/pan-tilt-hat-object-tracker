"""Run your week-5 ToyTracker over a clip and report id births and switches.

    uv run python scripts/replay_toy_tracker.py ../footage/clip.mp4

Write the id-switch number down. In week 6 you will run the same clip through ByteTrack and
compare — that delta is the point of building a tracker by hand first.

"Switch" here is a heuristic, not ground truth: a new id born in a frame where an existing
track died nearby. Good enough to compare two trackers on the same clip, which is all it is
for.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from object_tracker.config import DEFAULT_CONF, DEFAULT_WEIGHTS
from object_tracker.detection.yolo import YoloDetector
from object_tracker.device import resolve_device
from object_tracker.sources import FileSource
from object_tracker.toy_tracker import ToyTrackerState, update

NEARBY_PX = 100.0  # a birth this close to a death is counted as a probable switch


def _centers(detections) -> list[tuple[float, float]]:
    return [((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0) for b in detections.xyxy]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("--weights", default=DEFAULT_WEIGHTS)
    p.add_argument("--conf", type=float, default=DEFAULT_CONF)
    p.add_argument("--device", default="auto")
    args = p.parse_args(argv)

    detector = YoloDetector(args.weights, args.conf, None, resolve_device(args.device))
    source = FileSource(args.source)

    state = ToyTrackerState()
    seen_ids: set[int] = set()
    switches = 0

    try:
        for frame_idx, frame in enumerate(source):
            prior_tracks = {t.track_id: t.xyxy for t in state.tracks}
            tracked, state = update(state, detector.detect(frame), frame_idx)
            live = {t.track_id for t in state.tracks}

            born = {int(t) for t in (tracked.tracker_id if tracked.tracker_id is not None else [])}
            born -= seen_ids
            died = set(prior_tracks) - live

            for new_id in born:
                idx = list(tracked.tracker_id).index(new_id)
                cx, cy = _centers(tracked)[idx]
                for dead_id in died:
                    dx1, dy1, dx2, dy2 = prior_tracks[dead_id]
                    dcx, dcy = (dx1 + dx2) / 2.0, (dy1 + dy2) / 2.0
                    if np.hypot(cx - dcx, cy - dcy) < NEARBY_PX:
                        switches += 1
                        break
            seen_ids |= born
    finally:
        source.release()

    print(f"{len(seen_ids)} tracks born, {switches} probable id switches over {frame_idx + 1} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
