---
description: Install a previously reviewed resource into your Claude Code setup.
argument-hint: <slug>
---

Use the `resource-reviewer` skill to apply the previously reviewed resource: $ARGUMENTS

The skill should:

1. Locate the review by slug in `~/.claude/resource-reviews/`.
2. Route by classification:
   - Loose skill / command / agent → copy into `~/.claude/` or `.claude/`.
   - Full plugin → invoke `/plugin install`.
   - MCP server → show diff against `settings.json`, confirm, then patch.
   - Article / prompt → offer to extract into a CLAUDE.md draft instead.
3. Default to user scope unless overridden (remember the preference).
4. Always show a diff and confirm before any destructive action.

Full behavior is defined in `docs/SPEC.md`.
