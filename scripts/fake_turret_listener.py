"""A no-hardware stand-in for the Pi: listen for UDP Aim Commands and print them.

Run this in one terminal, then run the tracker with `--turret 127.0.0.1` in another
to watch the exact (pan_delta, tilt_delta, seq) the turret would send a real servo —
no Raspberry Pi, no Pan-Tilt HAT required.

Reuses the real Pi-side decoder so what you see is what turret_pi would decode. Also
reverse-maps each delta back to the *implied pixel error* the Aim Controller saw, using the
same gains the tracker ran with (`error = delta / kp`, undoing tilt's sign flip). Pass `--kp`
/ `--max-deg` to match your `--turret-kp` / `--turret-max-deg`; the defaults mirror the CLI.

    python scripts/fake_turret_listener.py                    # 0.0.0.0:9000, default gains
    python scripts/fake_turret_listener.py --port 9000 --kp 0.1

Reading the error column: `+120px` means the target was 120px right of / below centre
(+x right, +y down). `(sat)` means the delta hit `--max-deg`, so the true error is only known
to be *at least* that (clamped). `(deadzone)` means the delta was 0 — the target was within
`--turret-deadzone-px` of centre, i.e. on target, so the exact error is unknown but small.
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

# Make the turret/ package importable without installing it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "turret"))

from turret_pi.wire import decode  # noqa: E402

# Mirror the CLI defaults (object_tracker.config): keep this tool truthful out of the box.
_DEFAULT_KP = 0.05
_DEFAULT_MAX_DEG = 5.0


def _implied_error(delta: float, kp: float, max_deg: float, *, invert: bool) -> str:
    """Reverse the P law ``delta = clamp(kp * error, ±max_deg)`` back to a pixel-error string.

    ``invert`` undoes the tilt axis' sign flip (``tilt_delta = -kp * error_y``) so the reported
    error stays in image coordinates (+x right, +y down). Clamp and deadzone are lossy, so those
    cases are labelled rather than given a false exact value.
    """
    if kp <= 0.0:
        return "n/a (kp<=0)"
    if delta == 0.0:
        return "~0 (deadzone)"
    error = (-delta if invert else delta) / kp
    saturated = abs(delta) >= max_deg - 1e-6
    return f"{'>=' if saturated else '~'}{error:+.0f}px{' (sat)' if saturated else ''}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=9000)
    p.add_argument("--kp", type=float, default=_DEFAULT_KP,
                   help=f"Aim Controller gain used to reverse-map pixel error (default {_DEFAULT_KP})")
    p.add_argument("--max-deg", type=float, default=_DEFAULT_MAX_DEG,
                   help=f"Per-step slew clamp, to flag saturated deltas (default {_DEFAULT_MAX_DEG})")
    args = p.parse_args(argv)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    print(f"fake turret listening on {args.host}:{args.port} — Ctrl-C to stop", file=sys.stderr)
    print(f"reverse-mapping error with kp={args.kp}, max-deg={args.max_deg}", file=sys.stderr)

    try:
        while True:
            payload, _addr = sock.recvfrom(4096)
            try:
                pan, tilt, seq = decode(payload)
            except ValueError as exc:
                print(f"  dropped bad datagram: {exc}", file=sys.stderr)
                continue
            err_x = _implied_error(pan, args.kp, args.max_deg, invert=False)
            err_y = _implied_error(tilt, args.kp, args.max_deg, invert=True)
            print(
                f"seq={seq:>5}  pan_delta={pan:+7.3f}  tilt_delta={tilt:+7.3f}"
                f"  |  err≈ x={err_x}  y={err_y}"
            )
    except KeyboardInterrupt:
        print("\nstopped", file=sys.stderr)
        return 0
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
