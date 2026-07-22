# yolo-byteTrack-sot

## Personal environment (ported for Claude Code cloud)

These imports carry the operator's global Claude Code setup at project scope so it
reproduces in cloud spaces where `~/.claude` is empty. See `.claude/README.md`.

@.claude/personal/instructions.md
@.claude/rules/ecc/common/coding-style.md
@.claude/rules/ecc/common/git-workflow.md
@.claude/rules/ecc/common/development-workflow.md
@.claude/rules/ecc/common/testing.md
@.claude/rules/ecc/common/code-review.md
@.claude/rules/ecc/common/security.md
@.claude/rules/ecc/common/performance.md
@.claude/rules/ecc/common/patterns.md
@.claude/rules/ecc/common/hooks.md
@.claude/rules/ecc/common/agents.md
@.claude/rules/ecc/python/coding-style.md
@.claude/rules/ecc/python/testing.md
@.claude/rules/ecc/python/security.md
@.claude/rules/ecc/python/patterns.md
@.claude/rules/ecc/python/fastapi.md
@.claude/rules/ecc/python/hooks.md

## Agent skills

### Issue tracker

Issues and PRDs are tracked as local markdown files under `.scratch/<feature>/` (no external tracker; PRs are not a triage surface). See `docs/agents/issue-tracker.md`.

### Triage labels

Default triage vocabulary — `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
