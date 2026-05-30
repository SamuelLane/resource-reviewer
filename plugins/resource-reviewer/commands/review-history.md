---
description: Browse past resource reviews; recheck deferred ones against your current stack.
argument-hint: [--deferred | --recheck]
---

Use the `resource-reviewer` skill to handle review history: $ARGUMENTS

Behavior:

- No flags: list every review with date, slug, verdict, classification, applied state.
- `--deferred`: only deferred verdicts, with their `revisit_triggers`.
- `--recheck`: re-run the fit analysis on every deferred review against the current stack snapshot; surface newly relevant ones with a prompt to review-and-apply.

Full behavior is defined in `docs/SPEC.md`.
