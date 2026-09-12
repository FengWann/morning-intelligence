# Module 07 — Brief Generation and Editorial Verification

## Outcome

Selected events become a concise Chinese intelligence brief with traceable evidence and safe treatment of disputed claims.

## Dependencies

- Module 06 — Importance Ranking and Selection

## Tasks

- [x] Define the structured generation input using selected Events and source evidence only.
- [x] Generate the required brief sections in Chinese while preserving important English names and terms.
- [x] Produce a separate `speech_text` without raw URLs or Markdown mechanics.
- [x] Compare with the previous seven completed archives for the “What Changed?” section.
- [x] Avoid describing repeated coverage as a trend.
- [x] Separate confirmed facts, attributed claims, and system analysis.
- [x] Require two credible independent sources or a single-source warning for disputed political claims.
- [x] Represent materially different credible accounts without asserting false certainty.
- [x] Verify that every selected event has at least one valid evidence URL.
- [x] Check that generated claims do not exceed supplied evidence.
- [x] Enforce the 10–15 minute spoken-length target using an explicit character or estimated-duration check.
- [x] Add a fixture-based editorial check including a disputed event and insufficient-history case.

## Verification

Generate a fixture brief and confirm its structure, evidence links, warning labels, speech length, and fact/claim separation automatically. Perform one manual read-through before completing the module.

Verified 2026-09-12: fixture output was manually reviewed for readable section order,
clear fact/claim/analysis labels, distinct disputed accounts, evidence links, history
warning, and URL-free speech text. `pytest` passed 44 tests at 96% total coverage;
`mypy` strict, `ruff check`, and `ruff format --check` all passed.

## Done when

Every task above is checked and the verification command passes.
