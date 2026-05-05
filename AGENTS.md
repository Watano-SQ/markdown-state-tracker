# AGENTS.md

## Repository

This repository is `Markdown State Tracker`, a local prototype that processes Markdown files into a reusable status document.

Current code path:

1. Scan `input_docs/`
2. Detect changed documents
3. Chunk and store content in SQLite
4. Optionally run LLM extraction
5. Aggregate `state_candidates` into `states`
6. Generate `output/status.md`

Important current-state note: the repository now has a basic aggregation path from `state_candidates` into populated `states` for output. It also has minimal pending chunk recovery and a pending `retrieval_candidates` pool. Do not describe the full failed-chunk state machine, relation persistence, or full retrieval lifecycle/candidate adjudication as solved.

## Required Checks

Validation commands are maintained in [docs/testing.md](/D:/Apps/Python/lab/personal_prompt/docs/testing.md). Run the smallest relevant subset from that document for the task you are doing.

Use with care:

```bash
python main.py --init
```

`--init` deletes and rebuilds the SQLite database.

There is no repository-configured lint, typecheck, or CI command to claim by default. If that changes later, add it here.

## Red Lines

- Do not invent implemented behavior that the current code does not provide.
- Do not present planned aggregation/state-management behavior as current reality.
- Do not run `python main.py --init` unless the task requires it and the data loss is acceptable.
- Do not expose secrets from `.env`.
- Treat `input_docs/` as potentially real or sensitive content; avoid copying large excerpts into summaries unless necessary.
- Do not add heavy infrastructure that the repository explicitly excludes: web services, REST APIs, heavy databases, network search, or platform-scale redesign.
- Do not claim lint/typecheck/test coverage that does not exist in the repository.

## Reference Files

- [README.md](/D:/Apps/Python/lab/personal_prompt/README.md)
- [docs/architecture.md](/D:/Apps/Python/lab/personal_prompt/docs/architecture.md)
- [docs/testing.md](/D:/Apps/Python/lab/personal_prompt/docs/testing.md)
- [docs/specs/_template.md](/D:/Apps/Python/lab/personal_prompt/docs/specs/_template.md)
- [docs/plans/_template.md](/D:/Apps/Python/lab/personal_prompt/docs/plans/_template.md)
- [docs/specs/contextual_bundle_reading_view.md](/D:/Apps/Python/lab/personal_prompt/docs/specs/contextual_bundle_reading_view.md)
- [docs/plans/contextual_bundle_reading_view.md](/D:/Apps/Python/lab/personal_prompt/docs/plans/contextual_bundle_reading_view.md)
- [docs/changes.md](/D:/Apps/Python/lab/personal_prompt/docs/changes.md)
- [.github/CONTRIBUTING.md](/D:/Apps/Python/lab/personal_prompt/.github/CONTRIBUTING.md)
- [.github/EXTRACTION_JSON_SCHEMA.md](/D:/Apps/Python/lab/personal_prompt/.github/EXTRACTION_JSON_SCHEMA.md)
- [main.py](/D:/Apps/Python/lab/personal_prompt/main.py)
- [db/schema.py](/D:/Apps/Python/lab/personal_prompt/db/schema.py)
- [layers/input_layer.py](/D:/Apps/Python/lab/personal_prompt/layers/input_layer.py)
- [layers/aggregator.py](/D:/Apps/Python/lab/personal_prompt/layers/aggregator.py)
- [layers/middle_layer.py](/D:/Apps/Python/lab/personal_prompt/layers/middle_layer.py)
- [layers/output_layer.py](/D:/Apps/Python/lab/personal_prompt/layers/output_layer.py)
- [layers/extractors/llm_extractor.py](/D:/Apps/Python/lab/personal_prompt/layers/extractors/llm_extractor.py)

## Work Rules

- Prefer code and runnable commands over prose when establishing facts.
- Keep changes minimal and local to the task boundary.
- If information cannot be derived reliably from code or repository docs, mark it as `需要人类补充` instead of guessing.
- Use retained docs as the active source of truth. Use `docs/archive/` only for historical context.
- When a task changes commands, file layout, module boundaries, schema, or long-lived workflow rules, update the matching retained docs.
- Do not expand root documentation with task-specific plans; put task intent in `docs/specs/` and execution detail in `docs/plans/`.
- Keep only the current active implementation pair in `docs/specs/` and `docs/plans/` alongside `_template.md`; move superseded specs/plans to `docs/archive/specs/` and `docs/archive/plans/`.
- If a new spec/plan supersedes the active pair, archive the old pair in the same change and record the supersession in `docs/changes.md`.

## Documentation Sync Rule

After any non-trivial task, explicitly evaluate whether these files need updates:

- `AGENTS.md`
- relevant `docs/specs/*.md`
- relevant `docs/plans/*.md`
- relevant `docs/archive/specs/*.md` or `docs/archive/plans/*.md` when archiving or referencing superseded plans
- `docs/changes.md`
- `docs/architecture.md`

Update only the files whose source of truth actually changed.

In the final summary, always state:

1. which of these files were updated
2. which were evaluated but left unchanged
3. why
