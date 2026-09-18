"""turret_pi — the Raspberry Pi side of the pan-tilt tracking turret (ADR-0013).

The Pi is the **actuator**: it applies Aim Commands to the servos and streams its camera.
All detection and tracking stays on the Mac. This package must never grow a torch dependency.

Every module here imports and unit-tests on the Mac, because the hardware SDKs are imported
**lazily** — ``adafruit_servokit`` only when no kit is injected, ``picamera2`` only under
``--csi``. That is what makes "write on the Mac, deploy to the Pi" possible.
"""
