# resource-reviewer

A Claude Code plugin marketplace hosting the **resource-reviewer** plugin: a setup-aware evaluator for resources (skills, agents, commands, MCP servers, prompts, articles) shared by creators.

You paste a URL. It reads what's there, looks at your actual setup, and tells you honestly whether it's worth installing. If yes, it installs it.

## Install

```
/plugin marketplace add github.com/samuellane/resource-reviewer
/plugin install resource-reviewer
```

Three new slash commands become available:

- `/review-resource <url>` — review a resource
- `/apply-resource <slug>` — install one you previously reviewed; for workflow articles it synthesizes a skill or command, and for build blueprints it scaffolds a ready-to-build project folder
- `/review-history [--deferred|--recheck]` — browse / recheck past reviews

## Layout

- [`plugins/resource-reviewer/`](plugins/resource-reviewer/) — the plugin
- [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json) — marketplace manifest
- [`docs/SPEC.md`](docs/SPEC.md) — full design spec
- [`CLAUDE.md`](CLAUDE.md) — working-style conventions for contributors

## Status

v0.3.0 — core plugin + a **router** that decides what a link should become: install as-is, synthesize a skill/command from a reusable workflow, or scaffold a **project seed** (a new folder with `CLAUDE.md` + a build brief) from a build blueprint. Every path validates and shows-before-write; the plugin never auto-builds an app — it sets up the project and hands off. Remaining for v1: live testing on real articles/blueprints, slash-command polish, and publishing to GitHub. See [`docs/SPEC.md`](docs/SPEC.md) §§ Synthesis flow, Project-seed flow.
