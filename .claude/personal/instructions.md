
# Security Guidelines

## Secrets

- NEVER hardcode API keys, tokens, passwords, or credentials in any file
- Always use environment variable references: `${VAR_NAME}` or `process.env.VAR_NAME`
- Never echo, log, or print secret values to the terminal

## Permissions

- Never use `--dangerously-skip-permissions` or `--no-verify`
- Do not run `sudo` commands
- Do not use `rm -rf` without explicit user confirmation
- Do not use `chmod 777` on any file or directory

## Code Safety

- Validate all user inputs before processing
- Use parameterized queries for database operations
- Sanitize HTML output to prevent XSS
- Never execute dynamically constructed shell commands with user input

## MCP Servers

- Only connect to trusted, verified MCP servers
- Review MCP server permissions before enabling
- Do not pass secrets as command-line arguments to MCP servers
- Use environment variables for MCP server credentials

## Hooks

- All hooks must be reviewed before activation
- Hooks should not exfiltrate data or make external network calls
- PostToolUse hooks should validate output, not modify it silently

## Agent Selection

- When dispatching subagents for development work (planning, review, TDD, debugging, language-specific tasks), prefer the specialized `ecc:*` agents over the catch-all `general-purpose` agent
- Check `~/.claude/rules/ecc/common/agents.md` and the session's agent list for a matching `ecc:*` agent (e.g. `ecc:planner`, `ecc:architect`, `ecc:tdd-guide`, `ecc:code-reviewer`, `ecc:python-reviewer`, `ecc:security-reviewer`) before falling back to `general-purpose`
- Only use `general-purpose` or `Explore` when no `ecc:*` agent fits the task (e.g. broad open-ended codebase exploration)
