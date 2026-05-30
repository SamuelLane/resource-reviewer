"""Validate and (optionally) install a synthesized resource — a skill or command
generated from an article. stdlib only. Compatible with Python 3.9+.

Usage:
    echo '<candidate-json>' | python3 scaffold_skill.py [--confirm]

Input JSON (stdin):
    {
      "name": "my-skill",          # slug-safe; becomes the dir (skill) or file (command) name
      "output_type": "skill",      # "skill" | "command"
      "scope": "user",             # "user" | "project"
      "content": "---\\nname: ...", # full file text including YAML frontmatter
      "source_url": "https://..."  # optional; recorded only, not validated
    }

Without --confirm: prints a JSON plan — target path, collision flag (`exists`),
and structural validation results. Writes nothing.

With --confirm: re-validates, then atomically writes the file. If validation
fails it writes nothing and exits non-zero (the caller must not mark the review
applied).

This script enforces the *structural* floor (frontmatter present, name slug-safe
and matching, description and body substantial enough). Semantic quality is the
model's job in the synthesis self-critique step — see SKILL.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

USER_CLAUDE = Path.home() / ".claude"

NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
NAME_MIN, NAME_MAX = 1, 64
DESC_MIN, DESC_MAX = 16, 1024
BODY_MIN = 200


def scope_root(scope: str) -> Path:
    return USER_CLAUDE if scope == "user" else Path.cwd() / ".claude"


def split_frontmatter(content: str):
    """Return (frontmatter_dict, body) or (None, None) if no valid frontmatter."""
    if not content.startswith("---"):
        return None, None
    end = content.find("\n---", 3)
    if end == -1:
        return None, None
    fm_text = content[3:end].lstrip("\n")
    body = content[end + 4:].lstrip("\n")
    fm = {}
    for line in fm_text.split("\n"):
        if line.startswith((" ", "\t")) or ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, body


def validate(candidate: dict) -> list:
    problems = []
    name = candidate.get("name", "") or ""
    output_type = candidate.get("output_type", "skill")
    content = candidate.get("content", "") or ""

    if output_type not in ("skill", "command"):
        problems.append(f"output_type must be 'skill' or 'command', got '{output_type}'")

    if not (NAME_MIN <= len(name) <= NAME_MAX) or not NAME_RE.match(name):
        problems.append(
            f"name '{name}' must be slug-safe: lowercase a-z 0-9 and hyphens, "
            f"{NAME_MIN}-{NAME_MAX} chars, no leading/trailing hyphen"
        )

    fm, body = split_frontmatter(content)
    if fm is None:
        problems.append("content has no valid YAML frontmatter block (--- ... ---)")
    else:
        desc = fm.get("description", "")
        if not (DESC_MIN <= len(desc) <= DESC_MAX):
            problems.append(
                f"frontmatter 'description' must be {DESC_MIN}-{DESC_MAX} chars (got {len(desc)})"
            )
        if output_type == "skill":
            fm_name = fm.get("name", "")
            if fm_name != name:
                problems.append(
                    f"frontmatter 'name' ('{fm_name}') must match the resource name ('{name}')"
                )
        body_len = len(body.strip()) if body else 0
        if body_len < BODY_MIN:
            problems.append(
                f"body is too thin ({body_len} chars; need >= {BODY_MIN}) — "
                "the article is likely too vague to make a real skill"
            )

    return problems


def target_path(candidate: dict):
    name = candidate.get("name") or ""
    if not name:
        return None
    root = scope_root(candidate.get("scope", "user"))
    if candidate.get("output_type", "skill") == "command":
        return root / "commands" / f"{name}.md"
    return root / "skills" / name / "SKILL.md"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content if content.endswith("\n") else content + "\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--confirm", action="store_true",
                        help="Write the file. Without this flag, only a plan is printed.")
    args = parser.parse_args()

    try:
        candidate = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"scaffold_skill.py: invalid JSON on stdin — {e}\n")
        sys.exit(1)

    problems = validate(candidate)
    target = target_path(candidate)

    result = {
        "name": candidate.get("name"),
        "output_type": candidate.get("output_type", "skill"),
        "scope": candidate.get("scope", "user"),
        "target": str(target) if target else None,
        "exists": bool(target and target.exists()),
        "source_url": candidate.get("source_url"),
        "validation": {"ok": not problems, "problems": problems},
        "written": False,
    }

    if args.confirm:
        if problems or target is None:
            json.dump(result, sys.stdout, indent=2)
            sys.stdout.write("\n")
            sys.stderr.write("scaffold_skill.py: refusing to write — validation failed\n")
            sys.exit(2)
        atomic_write(target, candidate["content"])
        result["written"] = True

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
