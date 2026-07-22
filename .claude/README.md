# `.claude/` — ported personal environment

This directory carries the operator's Claude Code setup **at project scope** so the
same workflow reproduces in Claude Code cloud (claude.ai/code) and any fresh
environment where the user-level `~/.claude` is empty.

## What lives here

| Path | Purpose | Auto-loaded by |
|------|---------|----------------|
| `settings.json` | Marketplaces + enabled plugins, `env`, `model`, `permissions`, safety hooks | Claude Code at startup |
| `personal/instructions.md` | The operator's global `~/.claude/CLAUDE.md` (security + agent-selection rules) | `@import` in root `CLAUDE.md` |
| `rules/ecc/**` | Coding-style / testing / security / workflow rules | `@import` in root `CLAUDE.md` |
| `skills/learned/*.md` | Session-learned skills | reference (recall) |
| `memory/*.md` | Preserved project memory snapshot | reference (see note) |

## How the heavy stuff comes back (NOT copied here)

Plugins and everything inside them — the ECC agents, 278 skills, commands, ECC's own
hook graph — are **not** committed. They reinstall automatically from the public
marketplaces declared in `settings.json` (`extraKnownMarketplaces` + `enabledPlugins`)
the first time Claude Code starts in the cloud. Copying them would be redundant and
would drift out of date.

## Deliberately excluded

- **Broken `PreCompact` hook** — the global one pointed at a non-existent
  `~/.claude/hooks/memory-persistence/pre-compact.sh`; ECC's real memory hooks ship
  with the plugin.
- **`statusLine`** — depends on a machine-local `ccstatusline` binary.
- **`skipDangerousModePermissionPrompt`** — auto-skipping dangerous-permission prompts
  should not be committed to a shared repo.
- **`pyrefly` Stop hook** — requires `uv` + `pyrefly` in the environment; add it back
  under `hooks.Stop` in `settings.json` if the cloud image has them.
- **Secrets** — none are committed. Claude Code cloud uses your account auth. If a
  tool needs `GITHUB_TOKEN` etc., set it as a cloud environment variable, never here.

## Note on memory

Claude Code's live memory reads from `~/.claude/projects/<hash>/memory/`, which is
per-environment, so the cloud session starts with fresh memory. The files under
`memory/` are a preserved snapshot for reference and can be re-seeded if desired.
