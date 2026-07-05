# 01 — turret_pi hardware bring-up: post-merge follow-ups

Status: ready-for-agent

Tracked follow-ups from the final whole-branch review of the turret_pi hardware bring-up
(plan `docs/superpowers/plans/2026-07-05-turret-pi-hardware-bringup.md`, commits
`f194aa2..c79e897` on `docs/pan-tilt-turret-design`). The review verdict was **Ready to merge:
Yes** — zero Critical, zero Important. None of the below blocks merge; they are the accepted
trade-offs and minor nits, captured here so they are not forgotten.

## Accepted trust-model trade-offs (design decisions — revisit deliberately, do not "fix" blindly)

- **Unauthenticated control + stream planes.** UDP Aim Commands and the MJPEG stream are both
  unauthenticated; the stream binds `0.0.0.0`. Accepted per ADR-0013 (trusted, isolated LAN,
  single consumer). HMAC-signed datagrams are the proper fix and are the prerequisite before the
  turret drives anything dangerous — **needs-human** decision + a shared-key mechanism.
- **`--host` scopes only the control plane.** `run_streamer` has no bind-host/source-filter knobs,
  unlike `run_listener` (`host` + `allowed_source`). `turret --host 127.0.0.1` still exposes MJPEG
  on all interfaces. When HMAC lands, unify the two planes' trust posture (add `--stream-host` /
  a stream source filter, or document the asymmetry in `--host`'s help). The CLI help already reads
  "listener bind host", so this is low-impact today.
- **Single-threaded streamer can be camped by one client.** The Task-3 fix (single-threaded
  `HTTPServer`) is the correct call: `cv2.VideoCapture` is not thread-safe, and the
  `ThreadingHTTPServer` alternative raced and could crash on a normal reconnect. Multi-viewer
  support (a capture thread fanning out to per-connection queues) is out of scope / YAGNI until a
  real second consumer exists.

## Minor code follow-ups (agent-actionable, low priority)

- **Streamer observability cluster** (fold into one change): (a) log once on client disconnect
  instead of silently `break`/return in `do_GET`; (b) log when `_open_camera` fails inside the
  daemon streamer thread — today the thread dies silently and the turret keeps moving motors with
  no stream and no signal; (c) log once on streamer-loop exit. Gated on wiring `logging` into the
  module (the module currently suppresses `log_message` by design — keep the console quiet, use a
  logger).
- **No per-connection read timeout on the streamer.** `server.timeout` only bounds the wait for a
  *new* connection; a client that connects but never sends a request line blocks the single-threaded
  server until process exit. Same accepted availability class as the single-consumer trade-off, but
  a socket read timeout would harden it.
- **`servo._write` pan-then-tilt mid-write desync.** If the tilt I²C write raises after the pan
  write, recorded `_current` desyncs from the physical pose. No HW-error handling is in scope; today
  a raising `_write` propagates out of the listener loop → systemd restart → rebuild + recenter
  (self-healing). Add explicit handling only if/when I²C error recovery is designed.
- **`run_turret` type hint.** `driver: ServoDriver` could widen to the `Servo` Protocol
  (`listener.Servo`) to express the decoupling intent; runtime is unaffected (`main()` builds the
  concrete driver).
- **Sign-independent recenter test.** Add a test that monkeypatches `PAN_SIGN`/`TILT_SIGN` to `-1.0`,
  moves, then asserts `recenter()` still lands exactly on `CENTER` — guards against a future
  regression that routes recenter through `apply_delta`. (recenter is sign-independent by
  construction today.)
- **Teleop EOF guard.** `run_teleop`'s `sys.stdin.read(1)` busy-loops on EOF if driven
  non-interactively; a one-line `if not key: break` fixes it. Behind `# pragma: no cover`.

## Hardware bring-up checkpoints (needs the rig — from the plan's "Post-implementation" section)

Not code tasks. In order on the Pi: (1) `uv sync --extra hardware`, then `python -m turret_pi.teleop`
to calibrate `PAN_SIGN`/`TILT_SIGN` + pulse range and freeze the values into `servo.py`;
(2) live-verify the stream + measure end-to-end latency; (3) close the loop under systemd and confirm
the turret follows a target; (4) tune the P/PID gains. **needs-human / needs-hardware.**
