# AGENTS.md

## Scope

This directory contains runtime data such as the live SQLite database, logs, and temporary artifacts. It is not source code or disposable cache by default.

## Red Lines

- Do not delete `state.db` casually.
- Do not clear logs or temp artifacts unless the task explicitly requires cleanup or the files are clearly disposable runtime leftovers.
- Do not paste large raw log sections, database contents, or sensitive excerpts into summaries.
- Do not change the ignored status of `data/` casually; it is intentionally excluded by `.gitignore`.

## Work Rules

- Assume database rows and log lines may contain user-derived or sensitive content.
- Prefer counts, timestamps, filenames, and short redacted excerpts over raw dumps.
- If inspection is needed, summarize minimally and redact secrets or near-real personal details.
- If cleanup is performed, state exactly what was removed and why.
- If a task depends on destroying, sharing, or committing runtime data, mark the risk explicitly; if policy is unclear, mark it as `需要人类补充`.

## Sync

- Update `docs/testing.md` only if the expected runtime artifacts or inspection workflow changed.
- Update `docs/changes.md` if retention, cleanup, or data-handling rules change in a durable way.
