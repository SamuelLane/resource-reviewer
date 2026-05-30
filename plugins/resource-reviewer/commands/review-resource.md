---
description: Fetch a resource URL, evaluate it against your setup, and produce an honest review.
argument-hint: <url>
---

Use the `resource-reviewer` skill to evaluate the resource at: $ARGUMENTS

The skill should:

1. Classify the URL (GitHub repo / Google Doc / generic article).
2. Fetch its content via `scripts/fetch.py`.
3. Scan the user's setup via `scripts/inventory.py`.
4. Surface any deferred reviews from `~/.claude/resource-reviews/` that newly apply to the current stack.
5. Cross-reference resource vs. setup and produce a verdict (Adopt / Try alongside / Replace existing / Skip / Defer).
6. Write the review via `scripts/write_review.py`.
7. If the verdict warrants it, prompt to apply.

Full behavior is defined in `docs/SPEC.md`.
