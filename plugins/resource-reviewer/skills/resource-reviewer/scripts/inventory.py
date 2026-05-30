"""Scan the user's Claude Code setup. Outputs JSON to stdout.

Usage:
    python3 inventory.py [--project-path <path>]

Defaults --project-path to the current working directory. Reads from:
    - ~/.claude/CLAUDE.md + <project>/CLAUDE.md
    - ~/.claude/skills/ + <project>/.claude/skills/
    - ~/.claude/commands/ + <project>/.claude/commands/
    - ~/.claude/plugins/
    - ~/.claude/settings.json + <project>/.claude/settings.json (mcpServers)
    - <project>/docs/ (top-level filenames only)
    - <project> manifests: package.json, pyproject.toml, requirements.txt,
      Package.swift, Cargo.toml, Gemfile, go.mod
    - ~/.claude/resource-reviews/ (existing reviews — needed for recheck)

stdlib only. Compatible with Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HOME = Path.home()
USER_CLAUDE = HOME / ".claude"
SUMMARY_CAP = 300


def list_subdirs(path: Path) -> list[str]:
    if not path.exists():
        return []
    return sorted(
        p.name for p in path.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


def list_files(path: Path, ext: str | None = None) -> list[str]:
    if not path.exists():
        return []
    files = [p.name for p in path.iterdir() if p.is_file()]
    if ext:
        files = [f for f in files if f.endswith(ext)]
    return sorted(files)


def read_summary(path: Path, cap: int = SUMMARY_CAP) -> str | None:
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()[:cap]
    except Exception:
        return None


def list_installed_plugins() -> list[str]:
    """Read ~/.claude/plugins/installed_plugins.json. Keys are 'name@marketplace'."""
    manifest = USER_CLAUDE / "plugins" / "installed_plugins.json"
    if not manifest.exists():
        return []
    try:
        data = json.loads(manifest.read_text())
    except Exception:
        return []
    keys = (data.get("plugins") or {}).keys()
    names = sorted({k.split("@", 1)[0] for k in keys})
    return names


def parse_mcp_servers(settings_path: Path) -> list[str]:
    if not settings_path.exists():
        return []
    try:
        data = json.loads(settings_path.read_text())
    except Exception:
        return []
    return sorted((data.get("mcpServers") or {}).keys())


def detect_primary_tech(project_path: Path) -> list[str]:
    tech: set[str] = set()

    simple_markers = {
        "pyproject.toml": "python",
        "requirements.txt": "python",
        "Package.swift": "swift",
        "Cargo.toml": "rust",
        "Gemfile": "ruby",
        "go.mod": "go",
    }
    for fname, tag in simple_markers.items():
        if (project_path / fname).exists():
            tech.add(tag)

    pkg = project_path / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text())
            deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
            if "next" in deps:
                tech.add("nextjs")
            elif "react" in deps:
                tech.add("react")
            if "express" in deps:
                tech.add("express")
            if "fastify" in deps:
                tech.add("fastify")
            if "hono" in deps:
                tech.add("hono")
            tech.add("node")
        except Exception:
            tech.add("node")

    return sorted(tech)


def parse_review_frontmatter(path: Path) -> dict | None:
    """Very lightweight YAML frontmatter parser — only the fields we need."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    fm = text[3:end]

    meta: dict = {"_filename": path.name}
    triggers: list[str] = []
    in_triggers = False

    for raw_line in fm.split("\n"):
        if not raw_line.strip():
            continue
        if raw_line.startswith("revisit_triggers:"):
            in_triggers = True
            continue
        if in_triggers:
            stripped = raw_line.strip()
            if stripped.startswith("- "):
                triggers.append(stripped[2:].strip().strip('"').strip("'"))
                continue
            in_triggers = False
        if raw_line.startswith(" ") or raw_line.startswith("\t"):
            continue
        if ":" in raw_line:
            k, _, v = raw_line.partition(":")
            v = v.strip()
            if v:
                meta[k.strip()] = v.strip('"').strip("'")

    meta["revisit_triggers"] = triggers
    return meta


def list_reviews(reviews_dir: Path) -> list[dict]:
    if not reviews_dir.exists():
        return []
    out = []
    for f in sorted(reviews_dir.glob("*.md")):
        meta = parse_review_frontmatter(f)
        if meta:
            out.append(meta)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project-path", default=os.getcwd())
    args = parser.parse_args()

    project_path = Path(args.project_path).expanduser().resolve()

    project_skills = project_path / ".claude" / "skills"
    user_skills = USER_CLAUDE / "skills"

    project_commands = project_path / ".claude" / "commands"
    user_commands = USER_CLAUDE / "commands"

    user_settings = USER_CLAUDE / "settings.json"
    project_settings = project_path / ".claude" / "settings.json"

    snapshot = {
        "project_name": project_path.name,
        "project_path": str(project_path),
        "primary_tech": detect_primary_tech(project_path),
        "installed_skills_user": list_subdirs(user_skills),
        "installed_skills_project": list_subdirs(project_skills),
        "installed_commands_user": list_files(user_commands, ".md"),
        "installed_commands_project": list_files(project_commands, ".md"),
        "installed_plugins": list_installed_plugins(),
        "installed_mcp_servers": sorted(
            set(parse_mcp_servers(user_settings)) | set(parse_mcp_servers(project_settings))
        ),
        "user_claude_md_summary": read_summary(USER_CLAUDE / "CLAUDE.md"),
        "project_claude_md_summary": read_summary(project_path / "CLAUDE.md"),
        "docs_files": list_files(project_path / "docs", ".md"),
        "reviews": list_reviews(USER_CLAUDE / "resource-reviews"),
    }

    json.dump(snapshot, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
