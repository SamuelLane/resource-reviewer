"""Plan or execute the install of a reviewed resource.

Usage:
    python3 apply.py --slug <slug> --scope [user|project] [--confirm]

Without --confirm: prints a JSON plan describing what would happen. The
caller (the SKILL.md flow) shows the plan + any diff, gets user confirmation,
performs the actual file operations via Write/Edit/Bash, then re-invokes
this with --confirm.

With --confirm: marks the review file as applied (updates frontmatter)
and writes the user's scope preference to ~/.claude/resource-reviewer-config.json
if not already set. Does NOT perform file copies itself — those happen in
the caller because the resource content is fetched online.

stdlib only. Compatible with Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HOME = Path.home()
USER_CLAUDE = HOME / ".claude"
REVIEWS_DIR = USER_CLAUDE / "resource-reviews"
CONFIG_PATH = USER_CLAUDE / "resource-reviewer-config.json"


def load_review_path(slug: str) -> Path:
    candidates = sorted(REVIEWS_DIR.glob(f"*-{slug}.md"), reverse=True)
    if not candidates:
        sys.stderr.write(f"apply.py: no review found for slug '{slug}'\n")
        sys.exit(2)
    return candidates[0]


def parse_frontmatter(path: Path) -> tuple[dict, str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        sys.stderr.write(f"apply.py: review has no frontmatter: {path}\n")
        sys.exit(2)
    end = text.find("\n---", 3)
    if end == -1:
        sys.stderr.write(f"apply.py: frontmatter not closed: {path}\n")
        sys.exit(2)
    fm_text = text[3:end]
    body = text[end + 4 :]

    fields: dict = {}
    for line in fm_text.split("\n"):
        if line.startswith((" ", "\t")) or ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = v.strip()
        if v:
            fields[k.strip()] = v.strip('"').strip("'")
    return fields, body, text


def target_root(scope: str) -> Path:
    return USER_CLAUDE if scope == "user" else Path.cwd() / ".claude"


def build_plan(fields: dict, scope: str) -> dict:
    classification = fields.get("classification", "other")
    slug = fields.get("slug", "")
    url = fields.get("url", "")
    root = target_root(scope)

    actions: list[dict] = []

    if classification == "claude-code-skill":
        actions.append({
            "type": "copy_dir",
            "source_url": url,
            "target": str(root / "skills" / slug),
            "destructive": True,
            "note": "Copy the skill directory. If the target exists, show a unified diff and require confirmation first.",
        })
    elif classification == "claude-code-command":
        actions.append({
            "type": "copy_file",
            "source_url": url,
            "target": str(root / "commands" / f"{slug}.md"),
            "destructive": True,
            "note": "Write the command file. Diff against existing if present.",
        })
    elif classification == "claude-code-agent":
        actions.append({
            "type": "copy_file",
            "source_url": url,
            "target": str(root / "agents" / f"{slug}.md"),
            "destructive": True,
            "note": "Write the agent definition. Diff against existing if present.",
        })
    elif classification == "claude-code-plugin":
        actions.append({
            "type": "delegate_to_plugin_install",
            "marketplace_url": url,
            "command_hint": f"/plugin marketplace add {url} && /plugin install {slug}",
            "note": "Full plugins install via the marketplace, not by copying files.",
        })
    elif classification == "mcp-server":
        actions.append({
            "type": "patch_settings_json",
            "target": str(root / "settings.json"),
            "destructive": True,
            "note": "Compute the proposed mcpServers entry, show a unified diff of the file, require explicit y/N before patching.",
        })
    elif classification in ("workflow-article", "prompt-template"):
        actions.append({
            "type": "synthesize_resource",
            "default_output": "skill",
            "skill_target": str(root / "skills" / slug / "SKILL.md"),
            "command_target": str(root / "commands" / f"{slug}.md"),
            "claude_md_target": str(root / "CLAUDE.md"),
            "scaffold_script": "scaffold_skill.py",
            "destructive": True,
            "note": (
                "Not a copyable file. Run the Synthesis sub-flow (see SKILL.md): the model "
                "drafts a SKILL.md, self-critiques and revises once, then scaffold_skill.py "
                "validates it. Default output is a skill; offer slash-command or CLAUDE.md-draft "
                "as alternatives. Show the full generated content (and a diff if the target "
                "exists) and confirm before writing."
            ),
        })
    elif classification == "project-blueprint":
        actions.append({
            "type": "scaffold_project",
            "scaffold_script": "scaffold_project.py",
            "destructive": False,
            "builds_app": False,
            "note": (
                "A build blueprint, not an installable resource. Run the Project-seed sub-flow "
                "(see SKILL.md): propose a new project folder, generate CLAUDE.md + a self-contained "
                "build brief from the resource, validate with scaffold_project.py, show the full "
                "contents, and confirm before writing. Do NOT build the app — scaffold the seed and hand off."
            ),
        })
    else:
        actions.append({
            "type": "model_determined",
            "destructive": False,
            "note": (
                "No common-pattern match. Apply is NOT disabled: determine the most useful action "
                "for this resource yourself (install, synthesize a skill/command, scaffold a project "
                "seed, draft a doc, adjust config, or a combination), describe a short plan, and confirm "
                "before acting. Reuse scaffold_skill.py / scaffold_project.py where they fit. Stay within "
                "the safety rules — show-before-write, confirm destructive actions, never auto-build an app."
            ),
        })

    return {
        "slug": slug,
        "classification": classification,
        "scope": scope,
        "target_root": str(root),
        "url": url,
        "actions": actions,
    }


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception:
        return {}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def mark_applied(path: Path, scope: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace("applied: false", "applied: true", 1)
    text = text.replace("apply_scope: null", f"apply_scope: {scope}", 1)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--slug", required=True)
    parser.add_argument("--scope", choices=["user", "project"], default="user")
    parser.add_argument("--confirm", action="store_true",
                        help="Mark the review applied and persist the scope preference.")
    args = parser.parse_args()

    review_path = load_review_path(args.slug)
    fields, _, _ = parse_frontmatter(review_path)
    plan = build_plan(fields, args.scope)

    result: dict = {
        "review_path": str(review_path),
        "plan": plan,
    }

    if args.confirm:
        mark_applied(review_path, args.scope)
        cfg = load_config()
        if "default_scope" not in cfg:
            cfg["default_scope"] = args.scope
            save_config(cfg)
        result["applied"] = True
        result["default_scope_persisted"] = cfg["default_scope"]
    else:
        result["applied"] = False
        existing = load_config().get("default_scope")
        if existing:
            result["stored_default_scope"] = existing

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
