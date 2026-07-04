"""turret_pi — Pi-side actuator for the pan-tilt tracking turret (ADR-0013).

Runs on the Raspberry Pi only, as a separate installable package from ``object_tracker``
(different runtime host, disjoint dependency graph, different deploy lifecycle). This
package currently ships only the hardware-free pure units (``servo.ServoAngles`` /
``clamp_angles``, ``wire.decode``); the real I2C ``ServoDriver`` and the
streamer/listener/main entrypoint are a follow-up once Phase 0 hardware bring-up has settled
on a concrete HAT SDK.
"""

from __future__ import annotations
