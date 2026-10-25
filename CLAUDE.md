@AGENTS.md

## Claude Code specifics

- **Skills** (`.claude/skills/`): `/spec`, `/plan`, `/implement`, `/ship`, `/retro`, one for each stage in `docs/PROCESS.md`.
- **Subagents** (`.claude/agents/`): `code-reviewer` and `security-reviewer`. Run both before `/ship`.
- **Hooks** (`.claude/settings.json`): a guard hook blocks commands and edits that break the hard lines, and a format hook formats each file you edit. If a hook blocks you, don't look for a way around it. Fix the cause, or stop and ask.
- **Browser checks**: use the Playwright MCP server (`.mcp.json`) to check UI success criteria in a real browser.
