# ADR-0013: pan tilt turret as actuator sink

- **Status:** <!-- Proposed | Accepted | Superseded by ADR-XXXX -->
- **Week:** 9 — [`curriculum/week-09-servos.md`](../../curriculum/week-09-servos.md)
- **Date:** <!-- YYYY-MM-DD -->

## The question

Where does the turret fit in the architecture, and what runs on the Pi versus the Mac?

> **Guidance:** Three parts, written across weeks 9-11: (1) the Pi is the actuator, the Mac is the brain; (2) the wire protocol — fire-and-forget UDP, superseding commands, no shared module, and the trust model; (3) the Aim Controller — proportional first, PID only when the loop is seen to overshoot.

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
reference repo's `docs/adr/0013-pan-tilt-turret-as-actuator-sink.md` — not to check whether you matched it, but to see
where you weighed things differently.*
