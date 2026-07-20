"""turret_pi — Pi-side actuator for the pan-tilt tracking turret (ADR-0013).

Runs on the Raspberry Pi only, as a separate installable package from ``object_tracker``
(different runtime host, disjoint dependency graph, different deploy lifecycle). This
package ships the hardware-free units — ``servo.ServoAngles`` / ``clamp_angles``,
``wire.decode``, and ``listener.run_listener`` (the UDP command loop, which depends only on a
``Servo`` Protocol). Still a follow-up once Phase 0 hardware bring-up has settled on a
concrete HAT SDK: the real I²C ``ServoDriver``, the MJPEG ``streamer``, and the ``main``
entrypoint that injects the driver into the listener.
"""

from __future__ import annotations
