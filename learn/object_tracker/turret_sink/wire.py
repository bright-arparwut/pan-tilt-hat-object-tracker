"""Wire protocol — Mac-side half (ADR-0013). One JSON object per UDP datagram:
``{"pan_delta": ..., "tilt_delta": ..., "seq": ...}``.

**No shared module with the Pi side** (ADR-0013: separate deployables, separate dependency
trees). ``turret_pi.wire`` independently *decodes* the same documented shape. DRY says
extract a common module; the deployment boundary says don't. Understand the trade before you
"fix" it.
"""

from __future__ import annotations

import json

from .aim_controller import AimCommand


def encode(command: AimCommand, seq: int) -> bytes:
    """Encode one Aim Command as a UDP datagram payload.

    Coerce the deltas to plain ``float`` at this hardware-facing boundary. A numpy value
    (track centres are float32) raises "not JSON serializable" and crashes the control loop
    mid-run — with a motor moving.

    The root fix lives in ``tracking._present_centers`` (week 6). This is the
    belt-and-suspenders so a stray numpy type can never reach the wire. Two fixes for one bug
    is correct here: the cost is one ``float()`` call, and the failure mode is a crash next
    to moving hardware.
    """
    raise NotImplementedError("Week 10 — see learn/curriculum/week-10-wire-listener.md")
