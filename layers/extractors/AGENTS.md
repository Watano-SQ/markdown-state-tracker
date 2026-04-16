# AGENTS.md

## Scope

This directory owns extractor configuration, prompt text, request/response handling, retries, and parsing. Small changes here can affect cost, stability, and output structure.

## Red Lines

- Never expose API keys or other secrets from `.env` in code, logs, or summaries.
- Do not claim a provider or model is officially supported unless that support is verified in code and retained docs.
- Do not add unbounded retries or swallow parse/API failures silently.
- Do not log full chunk text or large raw model responses unless the task explicitly requires debug output and the privacy impact is acceptable.
- Do not move aggregation logic into the extractor path.

## Work Rules

- Keep prompt/schema changes synchronized with the structured output actually expected by code.
- If the extraction result shape changes, update `layers/middle_layer.py`, `.github/EXTRACTION_JSON_SCHEMA.md`, `test_extraction_schema.py`, and the prompt contract together.
- Keep preprocessing/postprocessing logic here or in `rule_helper.py`; keep state aggregation outside this directory.
- Active docs currently describe the default OpenAI path only. Archived multi-provider docs are historical context, not the current documentation promise.
- If provider behavior, cost, or support status cannot be verified from code, mark it as `需要人类补充`.

## Sync

- Update `docs/changes.md` when extractor behavior or support boundaries change in a long-lived way.
- Update `docs/architecture.md` only if extractor responsibilities or coupling to other layers materially changes.
