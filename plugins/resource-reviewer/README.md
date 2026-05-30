# resource-reviewer

A Claude Code plugin for honestly evaluating resources (skills, agents, commands, MCP servers, prompts, articles) shared by creators — before you install them.

## Commands

- `/review-resource <url>` — fetch, analyze, produce a verdict.
- `/apply-resource <slug>` — install a previously reviewed resource.
- `/review-history [--deferred|--recheck]` — browse past reviews; recheck deferred ones against your current stack.

## Install

```
/plugin marketplace add github.com/samuellane/resource-reviewer
/plugin install resource-reviewer
```

Default scope: user (`~/.claude/`). This is a meta-tool; you'll want it everywhere.

## Design

See [docs/SPEC.md](../../docs/SPEC.md) at the repo root for the full design — UX, data model, classification, history mechanics, and constraints.
