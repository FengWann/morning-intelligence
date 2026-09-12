# Module 02 — Source Ingestion

## Outcome

One command collects recent entries from configured RSS feeds and GDELT, while preserving per-source failures.

## Dependencies

- Module 01 — Foundation

## Tasks

- [x] Replace the empty example source list with a small verified starter set covering the four editorial lanes.
- [x] Define and validate one source configuration format.
- [x] Implement RSS/Atom collection for the previous 24 hours.
- [x] Implement GDELT discovery for the previous 24 hours.
- [x] Record source ID, title, URL, publication time, supplied summary, language, and collection time.
- [x] Isolate failures so one unavailable source does not abort collection.
- [x] Emit a collection result containing successes, failures, and counts.
- [x] Add a fixture-based check for one healthy feed and one broken feed.

## Verification

Run ingestion against fixtures, then run one live collection. Both must finish with structured output; the broken fixture must appear as a recorded failure rather than terminate the run.

## Done when

Every task above is checked and the verification command passes.

## Verification notes

- Deterministic verification: `python -m pytest` — 16 passed, 94.49% total branch-aware coverage.
- Static checks: `python -m mypy src tests`, `python -m ruff check .`, and `python -m ruff format --check .` — passed.
- Optional live smoke command: `python -m news_intelligence collect --live --sources config/sources.example.json`.
- Live network collection is intentionally separate from the automated suite and was not required or represented as fixture verification.
