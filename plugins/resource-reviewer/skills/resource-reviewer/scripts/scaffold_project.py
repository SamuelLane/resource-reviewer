"""Validate and (optionally) write a project seed — a new folder containing a
CLAUDE.md and a build brief, scaffolded from a build-blueprint resource. The
plugin sets up the project; it does NOT build the app. stdlib only. Python 3.9+.

Usage:
    echo '<candidate-json>' | python3 scaffold_project.py [--confirm]

Input JSON (stdin):
    {
      "project_name": "family-dashboard",      # slug-safe; becomes the folder name
      "parent_dir": "/Users/me/projects",       # where the folder is created (must exist)
      "files": {                                 # filenames -> content (basenames only)
        "CLAUDE.md": "...",                      # required, non-empty
        "BUILD-BRIEF.md": "..."                  # at least one brief, over the substance floor
      },
      "source_url": "https://..."                # optional; recorded only
    }

Without --confirm: prints a JSON plan — target path, collision state, validation.
With --confirm: validates, creates the folder, atomically writes each file. On
validation failure it writes nothing and exits non-zero.

This script does not build anything. It only writes the seed files.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$")
NAME_MIN, NAME_MAX = 1, 64
CLAUDE_MIN = 60
BRIEF_MIN = 200
CLAUDE_FILENAME = "CLAUDE.md"


def is_safe_filename(name: str) -> bool:
    return bool(name) and "/" not in name and "\\" not in name and ".." not in name


def dir_is_nonempty(path: Path) -> bool:
    return path.is_dir() and any(path.iterdir())


def validate(candidate: dict, target):
    problems = []
    name = candidate.get("project_name", "") or ""
    parent = candidate.get("parent_dir", "") or ""
    files = candidate.get("files")

    if not (NAME_MIN <= len(name) <= NAME_MAX) or not NAME_RE.match(name):
        problems.append(
            f"project_name '{name}' must be slug-safe (lowercase a-z 0-9 . _ -, "
            f"{NAME_MIN}-{NAME_MAX} chars, no leading/trailing separator)"
        )

    if not parent:
        problems.append("parent_dir is required")
    else:
        p = Path(parent).expanduser()
        if not p.exists():
            problems.append(f"parent_dir does not exist: {parent}")
        elif not p.is_dir():
            problems.append(f"parent_dir is not a directory: {parent}")

    if target is not None:
        if target.exists() and not target.is_dir():
            problems.append(f"target path exists and is not a directory: {target}")
        elif dir_is_nonempty(target):
            problems.append(
                f"target folder already exists and is not empty: {target} — "
                "refusing to scaffold over an existing project"
            )

    if not isinstance(files, dict) or not files:
        problems.append("files must be a non-empty object of {filename: content}")
    else:
        for fname in files:
            if not is_safe_filename(fname):
                problems.append(f"unsafe filename '{fname}' (basenames only, no '/' or '..')")

        claude = files.get(CLAUDE_FILENAME)
        if claude is None:
            problems.append(f"files must include a '{CLAUDE_FILENAME}'")
        elif len(claude.strip()) < CLAUDE_MIN:
            problems.append(
                f"{CLAUDE_FILENAME} is too thin ({len(claude.strip())} chars; need >= {CLAUDE_MIN})"
            )

        briefs = {k: v for k, v in files.items() if k != CLAUDE_FILENAME}
        if not briefs:
            problems.append("files must include at least one build brief besides CLAUDE.md")
        elif not any(len((v or "").strip()) >= BRIEF_MIN for v in briefs.values()):
            problems.append(
                f"no build brief clears the substance floor (need one file >= {BRIEF_MIN} chars) — "
                "the resource is likely too vague to scaffold a project"
            )

    return problems


def target_dir(candidate: dict):
    name = candidate.get("project_name") or ""
    parent = candidate.get("parent_dir") or ""
    if not name or not parent:
        return None
    return (Path(parent).expanduser() / name)


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
                        help="Create the folder and write files. Without this, only a plan is printed.")
    args = parser.parse_args()

    try:
        candidate = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"scaffold_project.py: invalid JSON on stdin — {e}\n")
        sys.exit(1)

    target = target_dir(candidate)
    problems = validate(candidate, target)
    files = candidate.get("files") if isinstance(candidate.get("files"), dict) else {}

    result = {
        "project_name": candidate.get("project_name"),
        "target": str(target) if target else None,
        "exists": bool(target and target.exists()),
        "files": sorted(files.keys()),
        "source_url": candidate.get("source_url"),
        "validation": {"ok": not problems, "problems": problems},
        "written": False,
    }

    if args.confirm:
        if problems or target is None:
            json.dump(result, sys.stdout, indent=2)
            sys.stdout.write("\n")
            sys.stderr.write("scaffold_project.py: refusing to write — validation failed\n")
            sys.exit(2)
        target.mkdir(parents=True, exist_ok=True)
        written = []
        for fname, content in files.items():
            atomic_write(target / fname, content)
            written.append(fname)
        result["written"] = True
        result["written_files"] = sorted(written)

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
