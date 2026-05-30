"""Read a review JSON from stdin and write it as markdown to ~/.claude/resource-reviews/.

Usage:
    echo '<review-json>' | python3 write_review.py

Input JSON shape (matches docs/SPEC.md § Data model):
    {
      "url": "...",
      "slug": "...",
      "date": "YYYY-MM-DD",            # optional, defaults to today
      "classification": "...",
      "verdict": "adopt|try-alongside|replace-existing|skip|defer",
      "verdict_reason": "...",
      "applied": false,
      "apply_scope": null,
      "stack_snapshot": { ... },
      "revisit_triggers": [ ... ],     # only for verdict=defer
      "quality_signals": { ... },
      "body": "<full review prose, markdown>"   # extracted; not in frontmatter
    }

Prints the saved file path to stdout. stdlib only. Compatible with Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REVIEWS_DIR = Path.home() / ".claude" / "resource-reviews"


def _scalar(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    needs_quote = (
        any(c in s for c in ':#\n"\'')
        or s.startswith((" ", "-", "[", "{", "&", "*", "|", ">", "!", "%", "@", "`"))
        or s.endswith(" ")
        or s.lower() in ("true", "false", "null", "yes", "no")
    )
    if needs_quote:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    return s


def _yaml(value, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(value, dict):
        if not value:
            return f"{pad}{{}}"
        lines = []
        for k, v in value.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{k}:")
                lines.append(_yaml(v, indent + 1))
            elif isinstance(v, (dict, list)):
                lines.append(f"{pad}{k}: {'{}' if isinstance(v, dict) else '[]'}")
            else:
                lines.append(f"{pad}{k}: {_scalar(v)}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{pad}[]"
        lines = []
        for item in value:
            if isinstance(item, dict):
                lines.append(f"{pad}-")
                lines.append(_yaml(item, indent + 1))
            else:
                lines.append(f"{pad}- {_scalar(item)}")
        return "\n".join(lines)
    return f"{pad}{_scalar(value)}"


def main() -> None:
    argparse.ArgumentParser(
        description="Write a review markdown file. Reads JSON from stdin; prints the saved path to stdout."
    ).parse_args()

    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"write_review.py: invalid JSON on stdin — {e}\n")
        sys.exit(1)

    slug = data.get("slug")
    if not slug:
        sys.stderr.write("write_review.py: 'slug' is required\n")
        sys.exit(1)

    date = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    data["date"] = date

    body = data.pop("body", "").strip()

    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    path = REVIEWS_DIR / f"{date}-{slug}.md"

    frontmatter = _yaml(data)
    content = f"---\n{frontmatter}\n---\n\n{body}\n" if body else f"---\n{frontmatter}\n---\n"

    path.write_text(content, encoding="utf-8")
    print(str(path))


if __name__ == "__main__":
    main()
