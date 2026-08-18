# resource-reviewer

You paste a URL. It reads what's there, looks at your actual setup, and tells you
honestly whether it's worth installing. If it is, it installs it.

A Claude Code plugin for evaluating shared resources — skills, agents, commands,
MCP servers, prompts, and articles — against the setup you actually have, instead
of the one the author assumed.

## Install

```
/plugin marketplace add github.com/samuellane/resource-reviewer
/plugin install resource-reviewer
```

Three slash commands become available:

- `/review-resource <url>` — review a resource
- `/apply-resource <slug>` — install one you reviewed earlier. For workflow
  articles it synthesizes a skill or command; for build blueprints it scaffolds a
  ready-to-build project folder.
- `/review-history [--deferred|--recheck]` — browse or recheck past reviews

## Layout

- [`plugins/resource-reviewer/`](plugins/resource-reviewer/) — the plugin
- [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json) — marketplace manifest
- [`docs/SPEC.md`](docs/SPEC.md) — full design spec
- [`CLAUDE.md`](CLAUDE.md) — working-style conventions for contributors

## Status

**v0.3.0.** The core plugin ships with a router that decides what a link should
become: install as-is, synthesize a skill or command from a reusable workflow, or
scaffold a project seed — a new folder with `CLAUDE.md` and a build brief — from a
build blueprint.

Every path validates and shows before it writes. The plugin never auto-builds an
app; it sets up the project and hands off.

Ahead of v1: live testing against real articles and blueprints, and slash-command
polish.
