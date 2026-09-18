# ADR-0014: sentry mode host side sweep dead reckoned pose

- **Status:** <!-- Proposed | Accepted | Superseded by ADR-XXXX -->
- **Week:** 12 — [`curriculum/week-12-sentry-integration.md`](../../curriculum/week-12-sentry-integration.md)
- **Date:** <!-- YYYY-MM-DD -->

## The question

With no pose feedback from the Pi, how can the host sweep the turret when no target is locked?

> **Guidance:** The section that matters is the drift analysis: pan self-corrects at the hard limits every half sweep, tilt has no such re-zeroing point, and its bounded drift is ACCEPTED. Argue why adding a feedback channel is the wrong fix.

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
reference repo's `docs/adr/0014-sentry-mode-host-side-sweep-dead-reckoned-pose.md` — not to check whether you matched it, but to see
where you weighed things differently.*
