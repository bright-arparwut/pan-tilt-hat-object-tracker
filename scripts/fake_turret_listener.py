"""A no-hardware stand-in for the Pi: listen for UDP Aim Commands and print them.

Run this in one terminal, then run the tracker with `--turret 127.0.0.1` in another
to watch the exact (pan_delta, tilt_delta, seq) the turret would send a real servo —
no Raspberry Pi, no Pan-Tilt HAT required.

Reuses the real Pi-side decoder so what you see is what turret_pi would decode.

    python scripts/fake_turret_listener.py            # listen on 0.0.0.0:9000
    python scripts/fake_turret_listener.py --port 9000
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

# Make the turret/ package importable without installing it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "turret"))

from turret_pi.wire import decode  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=9000)
    args = p.parse_args(argv)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    print(f"fake turret listening on {args.host}:{args.port} — Ctrl-C to stop", file=sys.stderr)

    try:
        while True:
            payload, _addr = sock.recvfrom(4096)
            try:
                pan, tilt, seq = decode(payload)
            except ValueError as exc:
                print(f"  dropped bad datagram: {exc}", file=sys.stderr)
                continue
            print(f"seq={seq:>5}  pan_delta={pan:+7.3f}  tilt_delta={tilt:+7.3f}")
    except KeyboardInterrupt:
        print("\nstopped", file=sys.stderr)
        return 0
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
