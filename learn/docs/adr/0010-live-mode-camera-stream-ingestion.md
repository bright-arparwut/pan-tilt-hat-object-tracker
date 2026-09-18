# ADR-0010: live mode camera stream ingestion

- **Status:** <!-- Proposed | Accepted | Superseded by ADR-XXXX -->
- **Week:** 8 — [`curriculum/week-08-live-mode.md`](../../curriculum/week-08-live-mode.md)
- **Date:** <!-- YYYY-MM-DD -->

## The question

How should Live mode be selected, and what must the loop stop assuming?

> **Guidance:** Mode inferred from --source shape, not a --live flag. The section that makes this honest is Throughput: live is NOT realtime, and you must say what that means for a --record file.

## Context

<!-- What is true that forces a decision? Constraints, measurements, prior ADRs. -->

## Decision

<!-- What you decided, in one or two sentences, in the active voice. -->

## Consequences

<!-- What this makes easy. What it makes hard. What you are now unable to do.
     An ADR without this section is a press release. -->

## Alternatives considered

<!-- What else you weighed, and the specific reason you rejected each one.
     "It was worse" is not a reason. -->

---

*Write this before you write the code. When it is done, diff your reasoning against the
reference repo's `docs/adr/0010-live-mode-camera-stream-ingestion.md` — not to check whether you matched it, but to see
where you weighed things differently.*
