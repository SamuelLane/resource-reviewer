"""Classify a resource URL and fetch what we can. Outputs JSON to stdout.

Usage:
    python3 fetch.py <url>

Output JSON shape:
    {
      "url": "<input>",
      "classification": "github_repo" | "google_doc" | "generic",
      "fetched_at": "<iso8601>",
      "github": { ... }       # only for github_repo
      "note": "..."           # only for google_doc / generic (instructs caller to WebFetch)
    }

stdlib only. Compatible with Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

GITHUB_URL_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/?#]+)")
GDOC_URL_RE = re.compile(r"^https?://docs\.google\.com/document/")
TIMEOUT = 10
README_CAP_CHARS = 8000


def classify(url: str) -> str:
    if GITHUB_URL_RE.match(url):
        return "github_repo"
    if GDOC_URL_RE.match(url):
        return "google_doc"
    return "generic"


def _http_get_json(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def _http_get_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_github(url: str) -> dict:
    m = GITHUB_URL_RE.match(url)
    owner, repo = m.group(1), m.group(2).rstrip("/").removesuffix(".git")

    try:
        meta = _http_get_json(f"https://api.github.com/repos/{owner}/{repo}")
    except urllib.error.HTTPError as e:
        # 403 most likely means rate-limited (unauthenticated GitHub)
        return {"owner": owner, "repo": repo, "error": f"GitHub API {e.code}: {e.reason}"}
    except Exception as e:
        return {"owner": owner, "repo": repo, "error": str(e)}

    default_branch = meta.get("default_branch", "main")

    try:
        contents = _http_get_json(f"https://api.github.com/repos/{owner}/{repo}/contents")
    except Exception:
        contents = []

    top_files = sorted(
        item["name"]
        for item in contents
        if isinstance(item, dict) and "name" in item
    )
    lower_top = {f.lower() for f in top_files}

    readme_excerpt = None
    for candidate in ("README.md", "readme.md", "README", "Readme.md"):
        try:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/{candidate}"
            readme_excerpt = _http_get_text(raw_url)[:README_CAP_CHARS]
            break
        except Exception:
            continue

    return {
        "owner": owner,
        "repo": repo,
        "description": meta.get("description"),
        "default_branch": default_branch,
        "stars": meta.get("stargazers_count"),
        "last_push": meta.get("pushed_at"),
        "open_issues": meta.get("open_issues_count"),
        "license": (meta.get("license") or {}).get("spdx_id") if meta.get("license") else None,
        "top_files": top_files,
        "has_readme": any(f.lower().startswith("readme") for f in top_files),
        "has_skill_md": "skill.md" in lower_top,
        "has_plugin_dir": ".claude-plugin" in lower_top,
        "has_commands_dir": "commands" in lower_top,
        "has_skills_dir": "skills" in lower_top,
        "has_agents_dir": "agents" in lower_top,
        "has_mcp_json": "mcp.json" in lower_top,
        "has_tests": any(t in lower_top for t in ("tests", "test", "__tests__", "spec")),
        "readme_excerpt": readme_excerpt,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url")
    args = parser.parse_args()

    out = {
        "url": args.url,
        "classification": classify(args.url),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    if out["classification"] == "github_repo":
        out["github"] = fetch_github(args.url)
    else:
        out["note"] = (
            "This script only directly fetches GitHub. "
            "For google_doc and generic URLs, use the WebFetch tool from the caller."
        )

    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
