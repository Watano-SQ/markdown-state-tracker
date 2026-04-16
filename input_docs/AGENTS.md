# AGENTS.md

## Scope

This directory contains raw input Markdown files and sample documents used by the pipeline. Some files may be close to real personal, team, or project content.

## Red Lines

- Treat all files here as potentially sensitive.
- Do not batch rewrite, normalize, reformat, or translate source documents unless the task is explicitly about input content.
- Preserve original structure, links, images, HTML fragments, and unusual formatting unless the task requires a targeted change.
- Avoid copying long raw excerpts into summaries, reviews, or logs.
- Do not add real sensitive documents as new samples. Prefer synthetic fixtures.

## Work Rules

- If a task needs a new sample document, add the smallest synthetic file that covers the case.
- If an existing sample must change, keep the edit minimal and explain why.
- Keep filenames, encoding, and line endings stable unless rename or re-encoding is part of the task.
- Deleting or replacing existing sample docs should be rare and task-driven.
- When summarizing this directory, prefer filenames, headings, counts, and paraphrases over direct quotation.
- If privacy expectations for a document are unclear, mark the gap as `需要人类补充`.

## Sync

- If sample documents are added, removed, or meaningfully repurposed for validation, update `README.md` or `TESTING.md` only if the documented workflow actually changed.
