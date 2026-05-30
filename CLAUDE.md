# resource-reviewer

A Claude Code plugin that lets users evaluate Claude Code resources (skills, agents, commands, MCP servers, prompts, articles) shared by creators — and decide whether they actually fit the user's setup before installing.

## What this project is

A distributable plugin published via the Claude Code plugin marketplace. Other developers install it once and get three slash commands:

- `/review-resource <url>` — fetch, analyze, and produce an honest evaluation
- `/apply-resource <slug>` — install a reviewed resource into their Claude Code setup
- `/review-history [flags]` — browse past evaluations, recheck deferred ones against current stack

## Source of truth

The full spec lives at `docs/SPEC.md`. Read it before making architectural decisions. It covers:

- Complete UX (install + use flows)
- Plugin file layout
- Resource-type handling (GitHub repos, public URLs/articles, public Google Docs)
- Apply mode (with show-diff-confirm)
- History mechanic (stack snapshots + revisit triggers)
- Data model for review records
- Known constraints and open questions

## Conventions

- `/docs` is the persistent memory layer. Major decisions get captured there, not in chat.
- The `SKILL.md` is the brain. Helper scripts in `scripts/` handle anything that needs real code — URL fetching, filesystem scanning, file installation.
- Show-diff-and-confirm before any destructive action (overwriting an installed skill, editing `settings.json` for an MCP install).
- Default to user scope (`~/.claude/`) for installs unless the user picks project scope; remember the preference after the first time.
- Distribution is via the Claude Code plugin marketplace only. No npm, no separate CLI.

## Working style

- Use `/effort high` for multi-file sessions touching `SKILL.md` plus scripts.
- When adding a new resource-type handler, update `docs/SPEC.md`'s scope section in the same change.
- Don't expand scope beyond what's in `docs/SPEC.md` without updating the spec first.
