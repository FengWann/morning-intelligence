# Module 06 — Importance Ranking and Selection

## Outcome

Events receive explainable scores and a balanced, non-duplicated set is selected for the daily brief.

## Dependencies

- Module 05 — Event Clustering

## Tasks

- [x] Implement the six scoring dimensions and weights defined in `SPEC.md`.
- [x] Store a short rationale for every dimension and total score.
- [x] Assign each candidate to Politics, Business, AI/Technology, or Singapore/Asia.
- [x] Prefer independent corroboration and authoritative primary sources.
- [x] Prevent one event from appearing in multiple sections.
- [x] Treat equal category allocation as a target, never a reason to include weak material.
- [x] Label single-source and low-confidence events.
- [x] Cap the selection to fit a 10–15 minute spoken brief.
- [x] Add a deterministic fixture check for ordering, category balance, and duplicate prevention.

## Verification

Run selection against the fixture event set. The result must be stable, contain no repeated event IDs, and include an explanation for every score.

Verified by `tests/test_ranking.py`, including deterministic reverse-input ordering,
four-lane round-robin balance, duplicate rejection, weak-item filtering, and the
900-second maximum spoken budget. The focused duplicate-only queue test exercises
duplicate skipping and clean queue exhaustion; `ranking.py` branch coverage is 100%.

## Done when

Every task above is checked and the verification command passes.
