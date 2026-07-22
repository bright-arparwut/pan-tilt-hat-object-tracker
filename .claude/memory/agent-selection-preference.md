---
name: agent-selection-preference
description: User wants ecc:* specialized agents used instead of the generic general-purpose agent for development work
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b5cad5ff-c514-4a61-8123-66ae3a39b8dd
---

When dispatching subagents for development tasks, prefer the specialized `ecc:*` agents (e.g. `ecc:python-reviewer`, `ecc:tdd-guide`, `ecc:planner`, `ecc:code-reviewer`, `ecc:architect`) over the catch-all `general-purpose` agent.

**Why:** The user has installed a full bench of ECC specialized agents covering planning, TDD, review, and language/framework-specific concerns (see the agent list in `~/.claude/rules/ecc/common/agents.md`). Reaching for `general-purpose` skips that tooling and gives generic, less-tailored results.

**How to apply:** Before calling the Agent tool for anything resembling planning, review, TDD, or a language-specific task, check whether an `ecc:*` agent already covers it (this project is Python, so `ecc:python-reviewer`, `ecc:tdd-guide`, `ecc:planner`, `ecc:architect`, `ecc:security-reviewer` are the relevant ones). Only fall back to `general-purpose` or `Explore` when no `ecc:*` agent fits the task (e.g. broad open-ended codebase exploration). This is a standing preference, not project-specific — apply it in any project where the ecc agent bench is available.
