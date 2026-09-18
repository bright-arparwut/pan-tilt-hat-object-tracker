"""A 1-D Kalman filter in ~30 lines, to be read and run — not the week-5 deliverable.

An object moves at constant velocity. Measurements are noisy, and between frames 10 and 15
they stop entirely (an occlusion). Watch the estimate coast through the gap on velocity
alone, and watch the uncertainty grow while it coasts.

    uv run python scripts/kalman_demo.py

See docs/kalman-note.md.
"""

from __future__ import annotations

import numpy as np

PROCESS_NOISE = 0.01       # how much we distrust the constant-velocity assumption
MEASUREMENT_NOISE = 4.0    # how much we distrust the detector. Try changing this.


def main() -> int:
    # State: [position, velocity]. Belief = mean x, covariance P.
    x = np.array([0.0, 0.0])
    P = np.eye(2) * 500.0          # start very unsure
    F = np.array([[1.0, 1.0], [0.0, 1.0]])   # constant velocity: pos += vel
    Q = np.eye(2) * PROCESS_NOISE
    H = np.array([[1.0, 0.0]])     # we measure position only, never velocity
    R = np.array([[MEASUREMENT_NOISE]])

    rng = np.random.default_rng(0)
    true_pos, true_vel = 0.0, 2.0

    print(f"{'frame':>5} {'truth':>8} {'measured':>10} {'estimate':>10} {'uncertainty':>12}")
    for frame in range(25):
        true_pos += true_vel

        # --- PREDICT: advance the belief, and grow the uncertainty ---
        x = F @ x
        P = F @ P @ F.T + Q

        occluded = 10 <= frame < 15
        if occluded:
            measured = None
        else:
            # --- UPDATE: blend prediction and measurement, and shrink the uncertainty ---
            measured = true_pos + rng.normal(0, np.sqrt(MEASUREMENT_NOISE))
            y = np.array([measured]) - H @ x          # innovation: what surprised us
            S = H @ P @ H.T + R
            K = P @ H.T @ np.linalg.inv(S)            # the Kalman gain: who to believe
            x = x + (K @ y).ravel()
            P = (np.eye(2) - K @ H) @ P

        shown = f"{measured:10.2f}" if measured is not None else "  (hidden)"
        print(f"{frame:>5} {true_pos:8.2f} {shown} {x[0]:10.2f} {P[0, 0]:12.2f}"
              + ("   <- coasting on velocity alone" if occluded else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
