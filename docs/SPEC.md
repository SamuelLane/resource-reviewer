# resource-reviewer — Specification

## Problem

Creators on social media regularly post Claude Code resources (skills, agents, commands, MCP servers, prompts, workflow guides) and often gate them behind engagement: "drop a comment and I'll DM you the link." The link arrives without context. Users have three bad options:

1. Install blindly and hope it doesn't conflict with what's already in their setup
2. Skim for 30 seconds and decide based on vibes
3. Bookmark and never come back

The result: low-quality resources get installed and forgotten, useful ones get missed, and users have no record of what they've already considered.

## Goal

A Claude Code plugin that takes a URL, fetches whatever's at it, compares it against the user's actual setup (current project, installed skills/plugins/MCP servers, CLAUDE.md context), and produces an honest evaluation in ~10 seconds. Optionally installs the resource if the verdict is positive. Logs every review for future reference.

The defining behavior: a user should be able to evaluate a creator's link with a single command and zero context-setting, and end up with either an installed resource that fits or a logged decision they can revisit later.

## Non-goals (v1)

- **Video resources (YouTube).** Out of scope — transcripts add a meaningful fetch dependency for marginal value at v1 scale.
- **X/Twitter threads.** Out of scope — auth-gated, fragmented.
- **Resources behind login walls** (private Notion, gated Substacks). Detect and surface the access error; let the user paste content manually if they want to proceed.
- **Multi-user / team marketplaces.** v1 is single-user.
- **Automated background scanning** for new resources from followed creators.
- **Partial install** of resource subcomponents (install only some files from a multi-skill repo). v1 is install-all-or-nothing.
- **Autonomous app-building.** For build-blueprints, the plugin scaffolds a project seed (a folder with `CLAUDE.md` + a build brief) and hands off. It does not build the application itself — that's a separate, user-driven session.

## Distribution

Standard Claude Code plugin, distributed via the plugin marketplace system.

Users install with:

```
/plugin marketplace add github.com/sam/resource-reviewer
/plugin install resource-reviewer
```

This is the only install path. No npm, no separate CLI. The plugin marketplace handles versioning and updates.

## Repo structure

```
resource-reviewer/
├── .claude-plugin/
│   └── marketplace.json
├── plugins/
│   └── resource-reviewer/
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── commands/
│       │   ├── review-resource.md
│       │   ├── apply-resource.md
│       │   └── review-history.md
│       ├── skills/
│       │   └── resource-reviewer/
│       │       ├── SKILL.md
│       │       └── scripts/
│       │           ├── fetch.py
│       │           ├── inventory.py
│       │           ├── write_review.py
│       │           ├── apply.py
│       │           ├── scaffold_skill.py
│       │           └── scaffold_project.py
│       └── README.md
├── docs/
│   └── SPEC.md   (this file)
├── CLAUDE.md
└── README.md
```

## User-facing UX

### Install (one-time)

```
> /plugin marketplace add github.com/sam/resource-reviewer
Added marketplace: resource-reviewer

> /plugin install resource-reviewer
Install scope:
  1. User (~/.claude/) — recommended for meta-tools
  2. Project (.claude/)
Choice [1]: 1

Installed resource-reviewer to ~/.claude/plugins/
Available commands: /review-resource, /apply-resource, /review-history
```

User picks user scope (recommended — this is a meta-tool used across projects). The three slash commands become available immediately, no restart.

### Review flow

User pastes a URL:

```
> /review-resource https://github.com/somecreator/backend-api-architect

Classifying… GitHub repo
Fetching README, SKILL.md, structure…
Scanning your setup: acme-ios (SwiftUI + Supabase)
Cross-referencing…

────────────────────────────────────────────────
VERDICT: Skip — wrong stack for this project

What it does
A "backend API architect" skill that generates Express/Fastify
endpoints from feature descriptions. Heavy Node.js focus.

Fit with your setup
Acme-ios is SwiftUI + Supabase. You don't run Node backends; your
backend logic lives in Supabase Edge Functions and Postgres RPCs.
No overlap with your installed skills.

Quality signals
Last commit 4 days ago. Solid README. 3 example workflows.
Author has 3 other published skills, mostly backend-focused.

→ Save as deferred (revisit if you add a Node backend)? [Y/n]
────────────────────────────────────────────────

Review saved: ~/.claude/resource-reviews/2026-05-27-backend-api-architect.md
```

The tool:

1. Classifies the URL (GitHub repo / Google Doc / generic article-like URL)
2. Fetches the content
3. Scans the user's setup (see Setup inventory below)
4. Cross-references the resource against the setup
5. Before producing the new review, checks past deferred reviews against the current stack and surfaces any that newly apply (see History flow)
6. Produces a structured inline review with a verdict
7. Writes the review to `~/.claude/resource-reviews/<date>-<slug>.md`
8. If the verdict warrants it, prompts for an apply action

### Verdict types

- **Adopt** — fills a real gap, fits the stack, quality signals are good
- **Try alongside** — no conflict with existing setup, worth experimenting with
- **Replace existing X** — overlaps with installed resource X, but is meaningfully better; offer to swap
- **Skip** — doesn't fit the stack, lower quality than alternatives, redundant with existing setup
- **Defer** — could matter later but doesn't fit current work; logged with revisit triggers

### Review output format

Inline summary shown in the Claude Code session:

```
VERDICT: <verdict> — <one-line reason>

What it does
<2-4 lines>

Fit with your setup
<2-5 lines covering overlap, gaps, conflicts>

Quality signals
<2-4 lines: maintenance, docs, tests, author signals>

Caveats
<optional, only if relevant>

→ <next-step prompt appropriate to verdict>
```

Persistent record also written to disk (see Data model).

### Apply flow

If the user accepts the apply prompt on an Adopt / Try alongside / Replace verdict:

```
→ Apply this resource?
   y  = install to user scope (~/.claude/skills/)
   p  = install to project scope (.claude/skills/, this project only)
   n  = don't install, save review only
Choice: y

Installing frontend-design-v2 to ~/.claude/skills/…
  → SKILL.md
  → scripts/extract-tokens.py
  → templates/
Done. Skill is active in this session.
```

The tool detects the resource type and routes appropriately:

- **Loose skill / command / agent** → copy files into the appropriate `~/.claude/` or `.claude/` directory
- **Full Claude Code plugin** → call `/plugin install` rather than copying files
- **MCP server** → show diff against current `~/.claude/settings.json` (or project-level settings), get explicit confirmation, then patch
- **Article / prompt template / workflow doc** → not a copyable file. Route to the **Synthesis flow** (below): generate a skill (default), a slash command, or a CLAUDE.md draft from the ideas, with self-critique, structural validation, and show-before-write.
- **Build blueprint** (a spec/guide/tutorial for building an app, dashboard, tool, or site) → route to the **Project-seed flow** (below): scaffold a new project folder with a `CLAUDE.md` and a self-contained build brief, ready to open in a fresh session. The plugin does **not** build the app itself.

On **Replace existing** verdicts, the apply step shows a diff between the installed version and the new version before proceeding.

The tool remembers the user's install-scope preference at `~/.claude/resource-reviewer-config.json` and stops asking after the first time, unless overridden with explicit `y` vs `p` in the same session.

### Synthesis flow (articles & prompt-templates → installable skills)

`workflow-article` and `prompt-template` resources aren't files you can copy — there's nothing installable in the source. Instead, apply *synthesizes* a new resource from the article's ideas. Default output is a **skill**; the user can switch to a slash command or the lightweight CLAUDE.md-draft at confirm time. Synthesis is **instructions-only** — it never generates helper scripts (a synthesized skill is prose: steps, rules, prompts).

Sub-flow:

1. **Draft.** The model writes a `SKILL.md` from the fetched article content: frontmatter (`name`, `description`) plus the workflow rewritten as procedural instructions Claude can follow. The `description` must name concrete trigger conditions, since it drives auto-triggering.

2. **Self-critique + revise once.** Before the user sees anything, the model grades its own draft against the rubric below and revises exactly once (one pass, not a loop — this bounds cost):
   - Is the `description` specific enough to auto-trigger at the right moment, and does it name concrete triggers?
   - Are the steps actionable instructions, not a vague restatement of the article?
   - Is everything grounded in the source? Nothing invented or hallucinated beyond what the article supports.
   - Is there enough substance to justify a skill at all?

3. **Validate.** `scaffold_skill.py` (no `--confirm`) structurally checks the candidate: frontmatter parses, `name` is slug-safe and matches the target directory, `description` is non-empty and within a sane length, body is non-empty and over a minimum substance threshold. If the article was too thin to yield a real skill, synthesis **refuses** here with a clear reason rather than installing a hollow skill. The model's self-critique catches semantic thinness; this script enforces the hard structural floor.

4. **Show + confirm.** The full generated `SKILL.md` is shown inline. The user can: approve as-is, request edits, switch output type (slash command / CLAUDE.md draft), rename the skill, change scope, or cancel. If the target already exists, a unified diff is shown first. Nothing is written before this.

5. **Install.** On approval, `scaffold_skill.py --confirm` atomically writes the resource to the chosen scope (`~/.claude/skills/<name>/SKILL.md` or the project equivalent; commands go to the corresponding `commands/<name>.md`). The review's frontmatter is then marked `applied: true`, with `synthesized: true` and the chosen `output_type` recorded so history reflects what was actually created.

### Project-seed flow (build-blueprints → a ready-to-build project folder)

Some resources aren't capabilities to install or reuse — they describe *building a specific thing* (a dashboard, an app, a tool, a site). For these (`project-blueprint`), apply doesn't install anything and doesn't build the app. It scaffolds a **project seed**: a new folder the user can open in a fresh Claude Code session and say "build this."

Telling a blueprint from a skill: a **skill** is a reusable procedure Claude should follow again and again (e.g. "how to run a code review"). A **blueprint** is a one-time artifact to construct (e.g. "build a family-activity dashboard"). When genuinely ambiguous, the recommendation is surfaced and the user can switch output type at confirm time.

The seed contains:

- `CLAUDE.md` — project context for the future build: what's being built, the implied or sensible-default stack, conventions, and a pointer to the build brief.
- A self-contained **build brief** (`BUILD-BRIEF.md`) — a high-level distillation of everything the resource specifies: goal, key features, data model, screens/components, and ordered build steps, plus the source URL for reference. Self-contained on purpose: the source link may be gated or temporary, so the details are captured in the file rather than only linked.

Sub-flow:

1. **Propose a location.** Suggest a sensible new folder (name derived from the resource; parent dir next to the user's existing projects). The user confirms or changes it, and can switch output type if the plugin guessed the kind wrong.
2. **Generate the files.** Draft `CLAUDE.md` and the build brief from the fetched resource content.
3. **Validate.** `scaffold_project.py` (no `--confirm`) checks the target folder isn't an existing non-empty project, the brief clears a substance floor, and `CLAUDE.md` is present and non-empty.
4. **Show + confirm.** Show the proposed folder path and the full contents of both files. Nothing is written before approval.
5. **Write + hand off.** On approval, `scaffold_project.py --confirm` creates the folder and writes the files. The plugin then **stops — it does not build.** It tells the user how to continue (open the folder, start the build). The review is marked `applied: true` with `output_type: project-seed` and the folder path recorded.

### History flow

Storage: `~/.claude/resource-reviews/`

Three entry points:

#### `/review-history`

List all past reviews:

```
> /review-history

2026-05-27  backend-api-architect    Skip          GitHub
2026-05-25  prompt-engineering-mega  Defer         Google Doc
2026-05-24  notion-search-mcp        Adopt ✓       GitHub
2026-05-22  react-component-skill    Try alongside GitHub
2026-05-20  ai-pm-workflow-article   Defer         Article

5 reviews · 1 applied · 2 deferred
```

#### `/review-history --deferred`

Show only the "defer" verdicts with their revisit triggers:

```
> /review-history --deferred

prompt-engineering-mega  (2026-05-25)
  Revisit if: working on long-form content generation
  Revisit if: building a copywriting tool

ai-pm-workflow-article  (2026-05-20)
  Revisit if: managing a multi-person team
  Revisit if: running structured product reviews
```

#### `/review-history --recheck`

Actively re-run the fit analysis on every deferred review against the user's current stack and surface anything newly relevant:

```
> /review-history --recheck

Scanning current stack: acme-web (Next.js + Supabase + multi-user)
Rechecking 2 deferred reviews…

⟳ ai-pm-workflow-article — now relevant
   Trigger matched: "managing a multi-person team"
   You're now collaborating with two teammates on Acme Web.
   Want to review and apply? [y/N]

prompt-engineering-mega — still deferred
   No trigger matches in current stack.
```

#### Automatic recheck

At the start of every `/review-resource` invocation, if any deferred reviews have revisit triggers matching the current state, they're surfaced inline before the new review begins.

## Data model

Each review is a markdown file with YAML frontmatter at `~/.claude/resource-reviews/<YYYY-MM-DD>-<slug>.md`:

```markdown
---
url: https://github.com/somecreator/backend-api-architect
slug: backend-api-architect
date: 2026-05-27
classification: claude-code-skill
verdict: defer
verdict_reason: "Wrong stack for current project but could matter later"
applied: false
apply_scope: null
stack_snapshot:
  project_name: acme-ios
  project_path: /Users/you/code/acme-ios
  primary_tech: [swiftui, supabase]
  installed_skills: [frontend-design, supabase-schema, swiftui-patterns]
  installed_mcp_servers: [supabase, posthog, notion]
  claude_md_summary: "consumer iOS app, SwiftUI + Supabase + a search API"
revisit_triggers:
  - "if you add a Node/Express backend to any project"
  - "if you start building a web frontend that needs its own API layer"
quality_signals:
  last_commit: 2026-05-23
  has_readme: true
  has_examples: true
  has_tests: false
  author_other_resources: 3
---

# Review: backend-api-architect

<full review prose mirroring the inline output>
```

For deferred reviews, `revisit_triggers` contains free-text conditions. The recheck logic evaluates these against the current stack snapshot.

## Resource type handling

### GitHub repos

Detect by domain (`github.com`). Use GitHub's API or raw content URLs to fetch:

- `README.md`
- `SKILL.md` / `plugin.json` / agent definition / `mcp.json` (for classification)
- Directory structure (top two levels)
- Last commit date, recent activity

Skip cloning unless content inspection requires it. For v1, public repos only — no auth.

### Google Docs

Detect by domain (`docs.google.com`). Attempt `web_fetch` against the public-view URL. If access is denied, return a clean error:

```
This Google Doc isn't publicly viewable. Either:
1. Change sharing to "anyone with the link can view" and run /review-resource again
2. Paste the content directly and I'll continue
```

### Generic URLs / articles

Anything else: `web_fetch`, then attempt to classify based on content. Article content may not be directly installable but can still be reviewed and converted into a CLAUDE.md draft contribution.

## Classification (common patterns — not a closed set)

Once content is fetched, identify what the resource is and, more importantly, the most useful **action** to take with it. The list below is a palette of common patterns to reason from — not buckets you must force a fit into. Claude picks the best fit, combines patterns, or goes beyond the list when the resource calls for it, and recommends an action the user can always redirect. A short `classification` label is still recorded for history, even when the action is bespoke.

- **claude-code-skill** — has a `SKILL.md` or matches the skill structure
- **claude-code-command** — markdown file in a `commands/` directory
- **claude-code-agent** — agent definition
- **claude-code-plugin** — has `.claude-plugin/plugin.json`
- **mcp-server** — has MCP server manifest or matches MCP server patterns
- **prompt-template** — system prompt / instructional template. **Installable via synthesis** into a skill (default) or slash command — see Synthesis flow.
- **workflow-article** — describes a workflow or process. Not a copyable file, but **installable via synthesis**: apply generates a skill (or command) from its ideas — see Synthesis flow.
- **project-blueprint** — a spec, guide, or tutorial for *building* something (an app, dashboard, tool, site). Not a reusable capability and not installable; apply scaffolds a **project seed** — a new folder with a `CLAUDE.md` and a self-contained build brief — see Project-seed flow.
- **other / bespoke** — doesn't match a common pattern. Apply is **not** disabled: Claude proposes the most useful action in plain language (install something, synthesize a skill, scaffold a project, draft a doc, adjust config, or something else), shows a short plan, and confirms before acting.

**Recommend, don't railroad.** The verdict's next step presents a *recommended* action with the reasoning, plus alternatives — never a forced multiple-choice. If the user wants a different outcome ("make it a skill instead", "just draft notes", "build it as its own app"), follow that. The taxonomy and the synthesis/project flows are defaults that make common cases fast, not limits on what Claude can do. All of it stays inside the safety rails: show-before-write, confirm destructive actions, never auto-build an app (see Non-goals), public resources only.

## Setup inventory

When a review runs, scan the following sources to build the stack snapshot:

- `~/.claude/CLAUDE.md` (user-global memory)
- `<project>/CLAUDE.md` (project-level memory)
- `<project>/docs/` (if present — read top-level filenames + first ~200 chars of each)
- `~/.claude/skills/` (user skills)
- `<project>/.claude/skills/` (project skills)
- `~/.claude/commands/` and `<project>/.claude/commands/`
- `~/.claude/plugins/` (installed plugins)
- `~/.claude/settings.json` (MCP servers, permissions, defaults)
- Project manifests: `package.json`, `pyproject.toml`, `Cargo.toml`, `Package.swift`, `Gemfile`, etc.
- `~/.claude/resource-reviews/` (review history — needed for the recheck step)

The inventory script outputs a structured summary the SKILL.md can reason against. Keep the summary compact — the SKILL.md doesn't need raw file contents, just the shape of the setup.

## Constraints / known issues

- **Private Google Docs** — surfaced gracefully but require manual sharing or paste-in.
- **Large GitHub repos** — fetch top-level + README only; deeper inspection only on request.
- **MCP server installs** — touch `settings.json`; always show diff and confirm.
- **Plugin vs skill detection** — if a resource is a full plugin (has `marketplace.json` or `plugin.json` at the right level), apply should route to `/plugin install` rather than file-copy.
- **Conflicts with installed resources** — replace-existing verdicts require explicit confirmation and show a diff first.
- **Scope preference persistence** — stored at `~/.claude/resource-reviewer-config.json`.
- **GitHub rate limits** — unauthenticated requests are limited. For v1, accept this and surface a clear error if hit; add optional `GITHUB_TOKEN` support in a later version.

## Open questions

1. **marketplace.json layout** — Sam's repo will both *be* the marketplace entry point and contain the plugin. Confirm the standard pattern against the current Anthropic plugin marketplace docs before finalizing the manifests.

2. **Stack-snapshot diffing for revisit triggers** — for "if you add a Node/Express backend" type triggers, how is the match computed? Plain string matching against the current snapshot's `primary_tech` and `claude_md_summary`? An LLM call? Lean toward string matching for v1 (cheaper, deterministic) and upgrade later if it's too brittle.

3. **Review index generation** — once there are 50+ reviews, the user may want a generated index file with categorization. Defer until it matters.

4. **Apply for partial matches** — if a fetched skill has subcomponents the user only wants some of, is partial install in scope? No for v1.

5. **Resource updates** — if a user reviewed and adopted a skill, then the upstream repo changes, is there a `/recheck-applied` flow? Out of scope for v1; can add later.

## Build order

1. **Repo skeleton** — `marketplace.json`, `plugin.json`, README placeholders, directory layout matching the spec
2. **SKILL.md** — get the core review logic right first; this is the brain. Write it before the scripts so the scripts know what they need to support
3. **`/review-resource` slash command** — thin wrapper around the skill
4. **`scripts/fetch.py`** — start with GitHub-only, expand to Google Docs and generic URLs
5. **`scripts/inventory.py`** — scan the user's setup and produce a structured summary
6. **`scripts/write_review.py`** — frontmatter + markdown output, write to `~/.claude/resource-reviews/`
7. **`/review-history` slash command** — list, `--deferred`, and `--recheck` flags
8. **Automatic recheck integration** — surface deferred reviews at the start of each `/review-resource`
9. **`scripts/apply.py` + `/apply-resource` slash command** — route by resource type, show diffs, confirm destructive actions
10. **README, install docs, screenshots** — polish for distribution
11. **Publish to GitHub, test install from a clean Claude Code session**
