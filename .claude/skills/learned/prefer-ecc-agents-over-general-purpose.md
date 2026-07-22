# Prefer ecc:* Specialized Agents Over general-purpose

**Extracted:** 2026-07-04
**Context:** Whenever dispatching a subagent (via the Agent tool) for development work — planning, review, TDD, debugging, language-specific tasks — in any project where the `ecc:*` agent bench is installed.

## Problem
`general-purpose` is a catch-all agent. Reaching for it by default skips a large bench of specialized `ecc:*` agents (planner, architect, tdd-guide, code-reviewer, security-reviewer, and per-language reviewers/build-resolvers) that are better tailored to the task and produce more targeted results.

## Solution
Before calling the Agent tool, check whether an `ecc:*` agent already matches the task type:
- Planning a feature/refactor → `ecc:planner`
- Architecture decision → `ecc:architect`
- New feature or bugfix needing tests-first → `ecc:tdd-guide`
- Code just written/modified → `ecc:code-reviewer` (or language-specific: `ecc:python-reviewer`, `ecc:go-reviewer`, `ecc:rust-reviewer`, etc.)
- Security-sensitive change → `ecc:security-reviewer`
- Build/compile failures → `ecc:build-error-resolver` or the language-specific `ecc:*-build-resolver`

Only fall back to `general-purpose` (or `Explore`, for pure read-only search) when no `ecc:*` agent fits — e.g. broad open-ended exploration that doesn't match any specialized role.

## Example
```
# BAD
Agent({ description: "Review new tracker code", subagent_type: "general-purpose", prompt: "..." })

# GOOD
Agent({ description: "Review new tracker code", subagent_type: "ecc:python-reviewer", prompt: "..." })
```

## When to Use
Any time you're about to invoke the Agent tool for development work in a project that has the ECC agent bench available (check `~/.claude/agents/` or the agent list surfaced at session start for `ecc:*` names). This is a standing user preference, not tied to one repo.
