# Module 05 — Event Clustering

## Outcome

Accepted articles describing the same real-world occurrence are grouped into stable Event records without merging articles that merely share a topic.

## Dependencies

- Module 04 — Private Archive and Run State

## Tasks

- [x] Implement the Event schema from `SPEC.md`.
- [x] Build candidate pairs using the event time window and normalized text.
- [x] Compare action, actor, organization, place, and topic compatibility.
- [x] Use Codex reasoning only for ambiguous candidate pairs.
- [x] Prefer separate clusters when the available evidence cannot establish identity.
- [x] Count independent source organizations rather than raw URLs.
- [x] Preserve stable event IDs during same-day reruns.
- [x] Persist dated Event records in the private archive.
- [x] Add fixtures for same-event coverage, same-topic/different-event coverage, updates, and syndicated copies.

## Verification

Run the clustering fixtures and inspect the generated Event records. Every expected merge and separation must match the fixture assertions.

Verified by `pytest tests/test_clustering.py`.

## Done when

Every task above is checked and the verification command passes.
