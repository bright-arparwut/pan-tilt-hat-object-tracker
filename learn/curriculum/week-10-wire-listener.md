# Week 10 — The command plane (UDP)

**Hours:** 4 Mac + 2 `[Pi]` · **Milestone:** drive the real servos from the Mac over UDP

## Why this week

A network now sits between the thing that decides and the thing that moves. Every choice this
week follows from one observation:

> **A stale command is worse than no command.**

If a nudge arrives 300ms late, applying it aims the turret at where the target *was*. So there
are no retries, no acks, no queue. UDP, fire-and-forget, freshest-wins. That is not laziness —
it's the correct protocol for superseding state, and knowing when to pick it is the lesson.

## Concepts

- **UDP vs TCP for control.** TCP guarantees delivery *eventually*, which for a control loop is
  the wrong guarantee — it head-of-line blocks and delivers stale commands in order. Understand
  why "reliable" is not always "better."
- **Supersede, don't queue.** Sequence numbers exist to **drop** old datagrams, not to reorder
  them. `seq <= last_seq` → discard.
- **The wedge bug, and the session gap.** A monotonic-only filter has a fatal flaw: the Mac
  restarts, its `seq` resets to 1, and the Pi ignores it **forever**. Or one bogus high-seq
  packet wedges it permanently. The fix is `SESSION_GAP_S` — after 1s of quiet, drop the seq
  gate and re-latch. Note the subtlety: **a dropped command never refreshes `last_ts`**, so the
  wedge self-heals. Make sure you see why.
- **No shared module between Mac and Pi.** `object_tracker/turret_sink/wire.py` encodes;
  `turret_pi/wire.py` decodes; neither imports the other. They're separate deployables with
  separate dependency trees. The cost is a documented shape both sides must honour; the benefit
  is that the Pi never grows a torch dependency. This is a real distributed-systems trade-off.
- **Pure core, thin loop.** `handle_datagram(payload, servo, state, now)` is pure — `now` is an
  *argument*, not a `time.monotonic()` call — so every staleness rule is testable without
  sockets or sleeps. `run_listener` owns only the socket. **This is the single best example of
  the project's spine; study it.**
- **Trust model, honestly stated.** This is an **unauthenticated** control plane: anyone who can
  reach the port drives your motors. `allowed_source` and a narrow bind host are
  defence-in-depth, **not** authentication — UDP source IPs are spoofable. The real fix is an
  HMAC over the payload. Read the security note in `listener.py` and understand why writing the
  limitation down is better than pretending.
- **Socket ownership.** A socket the loop *creates* it closes — even if `bind` raises (no leaked
  fd on `Address already in use`, the common fast-restart failure). An *injected* socket it
  never closes. Get this right; it's how the tests bind an ephemeral port.

## Sessions

**Session 1 (1.5h, Mac) — the wire, both halves.** `turret_sink/wire.encode` and
`turret_pi/wire.decode`. Independent implementations of one documented shape. `decode` raises
`ValueError` on anything malformed — one bad packet must never crash the loop. Note the
`float()` coercion in `encode` and its "belt-and-suspenders" comment (week 6's numpy bug again).

**Session 2 (2.5h, Mac) — the listener.** `handle_datagram` first, fully tested with a fake
servo and zero sockets: malformed → drop, stale-in-session → drop, post-gap → re-latch. Then
`run_listener` around it. Then `transport.UdpAimTransport` on the Mac side.

**Session 3 (2h, `[Pi]`) — close the command plane.** First on the Mac, no hardware:

```bash
uv run python scripts/fake_turret_listener.py --port 9000
```

Send it handcrafted datagrams and watch them decode. Then deploy and go live:

```bash
# Pi:   uv run turret --port 9000 --no-stream
# Mac:  send deltas from a python REPL via UdpAimTransport
```

The servos move, driven from your MacBook over the network. Then test the wedge case
deliberately: restart the sender, confirm the Pi re-latches after the gap.

## Files you implement

| File | What |
|---|---|
| `object_tracker/turret_sink/wire.py` | `encode` |
| `object_tracker/turret_sink/transport.py` | `AimTransport` Protocol, `UdpAimTransport` |
| `turret/turret_pi/wire.py` | `decode` |
| `turret/turret_pi/listener.py` | `Servo` Protocol, `ListenerState`, `handle_datagram`, `run_listener` |
| `turret/turret_pi/main.py` | `_parse_args`, `run_turret` (streamer thread comes in week 12) |

## Tests you're given

`turret/tests/test_wire.py::test_decode_rejects_malformed_payloads`,
`turret/tests/test_listener.py::test_a_stale_seq_within_the_session_is_dropped`,
`::test_the_seq_gate_is_dropped_after_a_quiet_gap_so_a_restarted_sender_relatches`,
`tests/test_turret_wire.py::test_encode_coerces_numpy_floats`

The re-latch test is the one that matters. It encodes a bug that would otherwise cost you an
evening of "why has my turret stopped responding."

## Tests you write

- A duplicate `seq` arriving twice in-session
- `run_listener` closes a socket it created even when `bind` raises
- `allowed_source` drops a datagram from an unexpected IP
- Round-trip: `encode` → `decode` preserves all three fields

## Milestone

Real servos moving in response to UDP datagrams sent from the Mac. No vision yet — just the
command plane, proven.

## ADR to write

**ADR-0013 (part 2) — the wire protocol: fire-and-forget UDP, superseding commands, no shared
module.** Include the trust model section. An ADR that omits its own security limitation isn't
finished.
