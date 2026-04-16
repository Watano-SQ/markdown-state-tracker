# AGENTS.md

## Scope

This directory defines the SQLite schema and connection behavior. It is a high-blast-radius area because SQL is also written directly in other modules.

## Red Lines

- Treat `python main.py --init` as destructive. Use it only when the task explicitly requires a rebuild and the data-loss impact is acceptable.
- Do not change schema for speculative cleanup or idealized redesign.
- Do not assume backward compatibility. The repository does not have a real migration framework.
- Before deleting or rebuilding database state, be explicit about the impact in commentary.

## Work Rules

- Prefer additive, minimal schema changes over broad table redesign.
- If `db/schema.py` changes, check and update affected SQL in `layers/input_layer.py`, `layers/middle_layer.py`, and `layers/output_layer.py`.
- If extraction-related tables or payload fields change, also check `.github/EXTRACTION_JSON_SCHEMA.md`, `test_extraction_schema.py`, and the extractor prompt contract.
- If a schema change requires resetting `data/state.db`, say so explicitly instead of implying compatibility.
- If compatibility or migration expectations cannot be inferred from code, mark them as `需要人类补充`.

## Sync

- Update `docs/architecture.md` when table responsibilities or storage boundaries change.
- Update `docs/changes.md` when a schema decision creates long-lived constraints or accepted debt.
