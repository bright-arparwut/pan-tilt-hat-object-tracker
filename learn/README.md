# `learn/` — the object-tracker sandbox

A skeleton of the project one directory up: **same architecture, empty bodies**. You
implement it, week by week, over 12 weeks at ~5–8 hrs/week.

The reference implementation lives at the repo root. It is the answer key — use it when
you're stuck, not before.

## How it works

Every module is present with its **module docstring, imports, type signatures and function
docstrings intact**. Only the bodies are gone:

```python
def select_target(present_ids: frozenset[int], prior_lock: int | None) -> int | None:
    """Lock-first-id (ADR-0013): keep ``prior_lock`` while it's present; otherwise lock
    the smallest present id. No ids present -> unlocked (``None``)."""
    raise NotImplementedError("Week 11 — see learn/curriculum/week-11-visual-servoing.md")
```

**The docstring is the spec.** It tells you what the function must do and why. Your job is
the how.

## What the tests give you

Each module ships **2–4 acceptance tests** — the contract, the ones that pin the behaviour
that actually matters (and the ones that catch the classic bug). The edge cases are yours
to write. A week isn't done until:

1. the given acceptance tests pass, **and**
2. you've added your own tests for the edges the week doc lists, **and**
3. the milestone command runs.

## Setup

```bash
cd learn
uv sync
uv run pytest                      # ~60 failures, nearly all NotImplementedError: week 0
uv run pytest tests/test_io.py     # week 1's target
```

The Pi package is separate, exactly as upstream:

```bash
cd learn/turret && uv sync         # Pi-side deps only
```

## Your workflow (Mac-first, deploy to Pi)

This is the workflow the real project uses, and months 1–2 are Mac-only anyway:

```
write + unit-test on the Mac   →   git push   →   git pull on the Pi   →   run
```

Every Pi-side module is importable on the Mac because its hardware imports are **lazy**
(`ServoDriver` only imports `adafruit_servokit` when no kit is injected; `streamer` only
imports `picamera2` under `--csi`). That is a deliberate design choice, and week 9 is where
you'll build it yourself. It means the pure logic — clamping, decoding, the listener's
per-datagram core — is fully testable on your MacBook with no hardware attached.

Only three things genuinely require the Pi: **I²C servo motion**, **camera capture**, and
**tuning the controller against real latency**. Those are the ~10 hours marked `[Pi]` in
the curriculum.

For the command plane you don't even need the Pi:

```bash
uv run python scripts/fake_turret_listener.py --port 9000   # terminal 1
uv run track --source 0 --track --turret 127.0.0.1:9000     # terminal 2
```

## The ADRs

`docs/adr/` holds **14 stubs** — title and the question each one answers, body empty. Write
each one in the week it comes up, *before* you read the original. Then diff your reasoning
against the root repo's. Deciding "should slicing be a decorator or a flag?" and writing
down why is half the point.

## Rules that make this work

1. **Don't read ahead in the root repo.** The answer key only teaches if you've struggled first.
2. **Pure function first, I/O wrapper second.** Every hard module in this project splits that
   way. If you can't unit-test it without hardware, you've put too much in the wrapper.
3. **Write the ADR before the code**, not after. It forces the decision to be conscious.
4. **Commit per week, with the week number in the message.** Your git log becomes the record
   of what you learned when.
