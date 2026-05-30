---
name: resource-reviewer
description: Evaluate Claude Code resources from URLs against the user's actual setup. Invoke when the user runs /review-resource <url> (fetch + evaluate + verdict + save), /apply-resource <slug> (install a reviewed resource), or /review-history [--deferred|--recheck] (browse or recheck past reviews). Produces verdicts of Adopt / Try alongside / Replace existing / Skip / Defer. Shows diffs before destructive actions. Logs every review.
---

# resource-reviewer

The brain behind the resource-reviewer plugin. Coordinates fetching a resource from a URL, scanning the user's Claude Code setup, producing an honest verdict, and (optionally) installing the resource. Every review is logged for future reference.

The full design spec is at `docs/SPEC.md` in the repo root. This file is the operational playbook for handling the three slash commands.

## Entry points

- `/review-resource <url>` → run the **Review flow**.
- `/apply-resource <slug>` → run the **Apply flow**.
- `/review-history [--deferred|--recheck]` → run the **History flow**.

## Companion scripts

All scripts live at `${CLAUDE_PLUGIN_ROOT}/skills/resource-reviewer/scripts/` and run with `python3` (stdlib only, no pip install needed).

- `fetch.py <url>` — classify the URL and fetch what's directly fetchable (GitHub metadata + README). Outputs JSON to stdout.
- `inventory.py [--project-path <path>]` — scan the user's setup. Outputs JSON to stdout.
- `write_review.py` — write a review markdown file. Reads JSON from stdin. Prints the resulting file path.
- `apply.py --slug <slug> --scope [user|project] [--confirm]` — plan or execute the install. Without `--confirm`, prints the plan only.

Invoke them with the Bash tool, capturing stdout as JSON.

## Review flow — `/review-resource <url>`

Goal: produce an honest, structured verdict in ~10 seconds and persist it.

### Step 1 — Pre-check deferred reviews

Before doing anything else, run `inventory.py` and scan its `reviews` list for entries with `verdict: defer`. For each, check whether any of their `revisit_triggers` now matches the current snapshot.

**Match logic (v1):** case-insensitive substring matching of each trigger against the joined text of `primary_tech`, `installed_skills_*`, `installed_mcp_servers`, `user_claude_md_summary`, and `project_claude_md_summary`. See SPEC § Open question 2 — this is intentionally simple for v1.

If any matches found, surface them inline before the new review:

```
⟳ Surfacing 1 previously deferred review that now applies:
  ai-pm-workflow-article (deferred 2026-05-20)
  Trigger matched: "managing a multi-person team"
  → I'll handle that one after this review if you want. Continuing with the new URL…
```

### Step 2 — Classify and fetch

Run `fetch.py <url>`. Parse the JSON. It tells you:

- `classification`: `github_repo` / `google_doc` / `generic`
- `github` (if github_repo): owner, repo, top-level files, README excerpt, last push date, etc.

For `google_doc` or `generic`, the script returns classification only — use the **WebFetch** tool to retrieve the content yourself.

If the URL is a Google Doc and WebFetch returns an access error, stop and reply:

```
This Google Doc isn't publicly viewable. Either:
  1. Change sharing to "anyone with the link can view" and run /review-resource again
  2. Paste the content directly and I'll continue
```

### Step 3 — Inventory the user's setup

Run `inventory.py` (you may have it cached from Step 1; reuse it). This snapshot is what you compare the resource against.

### Step 4 — Sub-classify the resource

Based on fetched content, identify what the resource is and — more importantly — the most useful **action** to take with it. The list below is a palette of common patterns, not a closed menu: pick the best fit, combine them, or go beyond them if the resource calls for it. Record a short `classification` label for history regardless.

- `claude-code-skill` — has a `SKILL.md` or matches the skill structure
- `claude-code-command` — markdown file in a `commands/` directory
- `claude-code-agent` — agent definition
- `claude-code-plugin` — has `.claude-plugin/plugin.json`
- `mcp-server` — has MCP server manifest or matches MCP patterns
- `prompt-template` — system prompt / instructional template
- `workflow-article` — describes a reusable workflow or process (installable via skill synthesis)
- `project-blueprint` — a spec / guide / tutorial for *building* something (an app, dashboard, tool, or site)
- `other` / bespoke — doesn't match a common pattern; apply is **not** disabled — you propose the most useful action yourself (see below)

**Skill vs. blueprint — the key distinction for articles.** A `workflow-article` is a *reusable procedure* Claude should follow repeatedly (→ synthesize a skill). A `project-blueprint` is a *one-time artifact to construct* (→ scaffold a project seed). "How to run a code review" is a skill; "build a family-activity dashboard" is a blueprint. If genuinely ambiguous, recommend the more likely one and let the user switch output type at the confirm step.

**Recommend, don't railroad.** Treat your classification as a recommendation, not a verdict the user must accept. In the next-step prompt, name the action you'd take and why, and make clear they can redirect to anything else — a skill, a project seed, a CLAUDE.md draft, a config change, or an outcome you propose on the spot. Determining the right thing to do is your job; the listed flows just make the common cases fast. Everything still happens inside the Safety rules below (show-before-write, confirm, never auto-build, public-only).

### Step 5 — Pick a verdict

Compare the resource against the snapshot honestly. Pick one:

- **Adopt** — fills a real gap, fits the stack, quality signals are good.
- **Try alongside** — no conflict with existing setup, worth experimenting with.
- **Replace existing X** — overlaps with installed resource X but is meaningfully better.
- **Skip** — wrong stack, lower quality than alternatives, or redundant.
- **Defer** — could matter later but doesn't fit current work. Requires `revisit_triggers`.

Be honest. Skip is a valid and often correct answer.

### Step 6 — Render the review inline

```
────────────────────────────────────────────────
VERDICT: <verdict> — <one-line reason>

What it does
<2–4 lines>

Fit with your setup
<2–5 lines covering overlap, gaps, conflicts>

Quality signals
<2–4 lines: maintenance, docs, tests, author signals>

Caveats
<optional, only if relevant>

→ <next-step prompt appropriate to verdict>
────────────────────────────────────────────────
```

Verdict-specific next-step prompts:

- **Adopt / Try alongside**: `Apply this resource? [y = user scope / p = project scope / n = skip]`
- **Replace existing X**: `Replace <X> with this? [y/n]` — and on `y`, show the diff before executing.
- **Skip**: no prompt; the review is still saved.
- **Defer**: `Save as deferred (revisit if <conditions>)? [Y/n]`

### Step 7 — Persist the review

Build a JSON object matching the SPEC § Data model frontmatter schema. Required fields:

- `url`, `slug`, `date` (YYYY-MM-DD), `classification`, `verdict`, `verdict_reason`
- `applied: false`, `apply_scope: null` (set later by apply.py)
- `stack_snapshot` — copy the relevant subset from the inventory output
- `revisit_triggers` — array of plain-English conditions (only for verdict=defer)
- `quality_signals` — last_commit, has_readme, has_examples, has_tests, author_other_resources
- `body` — the full review prose (mirrors the inline output without the box rules)

Pipe the JSON into `write_review.py` via stdin. It prints the saved file path. Surface that path:

```
Review saved: ~/.claude/resource-reviews/2026-05-27-backend-api-architect.md
```

### Step 8 — Apply prompt (if positive verdict)

If the verdict is Adopt / Try alongside / Replace existing AND the user accepted the inline apply prompt, immediately jump into the **Apply flow** with the slug just written. No need for the user to re-issue the command.

## Apply flow — `/apply-resource <slug>`

### Step 1 — Plan

Run `apply.py --slug <slug> --scope <scope>` (no `--confirm`). It reads the review, detects classification, and outputs a JSON plan describing what *would* happen — target paths, settings.json edits, etc.

Display the plan in human-readable form. For any operation that overwrites an existing file (Replace existing X, mcp-server installs, etc.), construct a unified diff using the existing file content vs. the proposed new content and show it inline.

### Step 2 — Confirm

Prompt:

```
Apply this resource?
   y  = install to user scope (~/.claude/)
   p  = install to project scope (.claude/, this project only)
   n  = don't install, keep review only
Choice: 
```

If a stored preference exists at `~/.claude/resource-reviewer-config.json`, skip the prompt and use it — but show the chosen scope inline so the user can see.

### Step 3 — Execute

Once confirmed, perform the actual file operations using the standard Write / Edit / Bash tools (the plan tells you what to do). The Python apply.py script intentionally does NOT perform the copies itself, because the resource content lives on the web and you (the model) are the one fetching it via WebFetch in Step 2 above.

After the file operations succeed, re-invoke `apply.py --slug <slug> --scope <scope> --confirm`. This marks the review file's frontmatter `applied: true` and records the scope.

If any operation fails, surface the error verbatim, leave `applied: false`, and stop.

### Step 4 — Special cases

- **Full plugin (`claude-code-plugin`)**: don't copy files. Tell the user to run `/plugin marketplace add <url>` (if it's a marketplace) then `/plugin install <name>`.
- **MCP server**: the diff against `settings.json` MUST be shown and confirmed. Never auto-patch.
- **Article / prompt template / workflow-article**: not a copyable file. Run the **Synthesis sub-flow** (below) to generate an installable skill (default), slash command, or CLAUDE.md draft from the ideas.
- **Project-blueprint** (a spec/guide for *building* an app, dashboard, tool, or site): run the **Project-seed sub-flow** (below). Scaffold a new project folder with `CLAUDE.md` + a build brief. Do **not** build the app.
- **Other / bespoke**: apply is **not** disabled. Determine the most useful action for this specific resource, describe it and a short plan, and confirm before doing anything. It might be a skill, a project seed, a doc edit, a settings change, or a combination — use judgment, stay within the Safety rules.

## Synthesis sub-flow (articles & prompt-templates)

When the classification is `workflow-article` or `prompt-template`, there's no file to copy — you generate a new resource from the article's ideas. Default output is a **skill**. Synthesis is **instructions-only**: never generate helper scripts.

### S1 — Draft

Using the fetched article content (you have it from the review flow; re-fetch with WebFetch if not), write a complete `SKILL.md`:

- Frontmatter `name` (slug-safe, derived from the article title) and `description`.
- The `description` must name concrete trigger conditions — when should Claude reach for this skill? This field drives auto-triggering; a vague description means the skill never fires.
- Body: the workflow rewritten as clear, ordered, actionable instructions. Not a summary of the article — an operational playbook Claude can follow.

### S2 — Self-critique and revise once

Before showing the user anything, grade your own draft against this rubric, then revise it **exactly once** (one pass — don't loop):

1. **Trigger quality** — is `description` specific enough to fire at the right moment, with concrete triggers named?
2. **Actionability** — are the steps real instructions, or just a restatement of the article?
3. **Grounding** — is everything traceable to the source article? Remove anything invented or assumed.
4. **Substance** — is there enough here to justify a skill? If the article is too thin, say so now.

If the rubric pass concludes the article is too thin to make a worthwhile skill, stop and tell the user plainly — offer the CLAUDE.md-draft fallback instead.

### S3 — Validate

Build the candidate JSON (`name`, `output_type`, `scope`, `content` = the full file text, `source_url`) and run `scaffold_skill.py` **without** `--confirm`. It returns a plan with structural validation results and a collision flag (`exists`).

If `validation.ok` is false, fix the reported problems (usually name / description / body issues) and re-run. If `exists` is true, you'll show a diff in the next step.

### S4 — Show and confirm

Show the user the complete generated `SKILL.md` inline. Offer:

- approve as-is,
- request edits (apply them, then re-validate via S3),
- switch output type — slash command (`commands/<name>.md`) or CLAUDE.md draft,
- rename the skill,
- change scope (user / project),
- cancel.

If `exists` is true, show a unified diff between the installed file and the new content first. Nothing is written before explicit approval.

### S5 — Install

On approval, re-run `scaffold_skill.py --confirm` with the final candidate. It atomically writes the resource and validates once more. Then re-run `apply.py --slug <slug> --scope <scope> --confirm` to mark the review `applied: true`. Record `synthesized: true` and the chosen `output_type` in the review (re-run `write_review.py` with those fields added if needed).

If `scaffold_skill.py` exits non-zero, surface the error verbatim, leave the review unapplied, and stop.

## Project-seed sub-flow (build-blueprints)

When the classification is `project-blueprint`, don't install and **don't build**. Scaffold a **project seed** — a new folder the user can open in a fresh session and say "build this."

### P1 — Propose a location

Suggest a new folder: a slug-safe name derived from the resource, in a sensible parent directory (next to the user's existing projects — infer from the current project path; default to the parent of the current working directory, or the home directory if unclear). Show the proposed full path. The user can change it, or switch output type if you classified wrong (skill / CLAUDE.md draft).

### P2 — Generate the files

From the fetched resource content, draft two files:

- `CLAUDE.md` — project context for the future build: what's being built, the implied or sensible-default stack, conventions, and a pointer to the build brief.
- `BUILD-BRIEF.md` — a self-contained, high-level distillation of everything the resource specifies: goal, key features, data model, screens/components, and ordered build steps. Include the source URL for reference, but capture the details in the file (the link may be gated or temporary).

### P3 — Validate

Build the candidate JSON (`project_name`, `parent_dir`, `files` = {filename: content}, `source_url`) and run `scaffold_project.py` **without** `--confirm`. It checks the target folder isn't an existing non-empty project, `CLAUDE.md` is present and non-empty, and the brief clears a substance floor. Fix any reported problems and re-run.

### P4 — Show and confirm

Show the proposed folder path and the full contents of both files. Nothing is written before explicit approval.

### P5 — Write and hand off

On approval, re-run `scaffold_project.py --confirm`. It creates the folder and writes the files. Then **stop — do not build.** Tell the user how to continue, e.g.:

```
Project seed created at ~/projects/family-dashboard/
  → CLAUDE.md
  → BUILD-BRIEF.md

To build it: open that folder in Claude Code and say
"read CLAUDE.md and BUILD-BRIEF.md, then let's build this."
```

Mark the review `applied: true` with `output_type: project-seed` and the folder path recorded (re-run `write_review.py` with those fields if needed). If `scaffold_project.py` exits non-zero, surface the error verbatim and stop.

### Scope preference

The first time the user picks a scope, write `{"default_scope": "user"|"project"}` to `~/.claude/resource-reviewer-config.json`. Future apply flows read this and skip the prompt unless overridden.

## History flow — `/review-history [flags]`

### No flags

List every review in `~/.claude/resource-reviews/` (use `inventory.py` to enumerate). Render as a table:

```
DATE        SLUG                     VERDICT          TYPE
2026-05-27  backend-api-architect    Skip             GitHub
2026-05-25  prompt-engineering-mega  Defer            Google Doc
2026-05-24  notion-search-mcp        Adopt ✓          GitHub
```

Append a summary line: `N reviews · M applied · K deferred`.

### `--deferred`

Filter to verdicts with `verdict: defer`. For each, show the `revisit_triggers` as a bulleted list under the slug.

### `--recheck`

Run the same trigger-matching logic from Review flow Step 1 against the current stack snapshot. For each deferred review whose trigger now matches:

```
⟳ <slug> — now relevant
   Trigger matched: "<text>"
   <one-line plain-English explanation of why it matches>
   Want to review and apply? [y/N]
```

If `y`, re-run a full Review flow (Steps 2–8) on the original URL — the user's stack may have changed enough that the fresh verdict differs from the old `defer`.

## Safety rules

- **Show diff and confirm before any destructive action.** Includes: overwriting an existing skill, patching `settings.json`, replacing an installed resource. No exceptions.
- **Default to user scope** unless the user explicitly picks project or has a stored preference.
- **Don't expand classification taxonomy** without updating `docs/SPEC.md` first.
- **Don't claim to install something you didn't.** If an apply step fails, leave `applied: false` and surface the error.
- **Public resources only in v1.** No authenticated GitHub, no private Google Docs. If access is denied, surface the error cleanly and let the user paste content manually.
