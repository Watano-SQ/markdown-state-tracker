# AGENTS.md

## Scope

This directory contains the current three-layer pipeline: input, middle, and output. The repository already has some cross-layer coupling; treat the existing layout as a real constraint, not as a blank slate.

## Red Lines

- Do not silently turn the current layer structure into a different architecture.
- Do not move logic across layers just for abstraction polish.
- Do not describe planned aggregation behavior as if the current layer boundaries already enforce it cleanly.

## Work Rules

- Keep scanning, diffing, and chunking concerns in `input_layer.py`.
- Keep extraction persistence, state storage, evidence, and stats concerns in `middle_layer.py`.
- Keep output selection and Markdown generation in `output_layer.py`.
- New modules inside `layers/` are allowed only when they preserve the current responsibilities and reduce maintenance risk.
- Prefer adapting to existing coupling over doing opportunistic refactors.
- The more specific rules in `layers/extractors/AGENTS.md` apply inside that subdirectory.

## Sync

- Update `docs/architecture.md` when module responsibilities, call direction, or cross-layer dependencies change materially.
- Update `docs/changes.md` when a change establishes a new long-lived boundary rule.
