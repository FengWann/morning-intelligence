# Module 03 — Normalization and Deduplication

## Outcome

Raw collected entries become valid Article records, and obvious duplicate coverage is identified deterministically.

## Dependencies

- Module 02 — Source Ingestion

## Tasks

- [x] Implement the Article schema from `SPEC.md`.
- [x] Normalize Unicode, whitespace, source identifiers, and timestamps.
- [x] Remove known tracking parameters and preserve a canonical URL.
- [x] Create stable article IDs and content hashes.
- [x] Reject entries missing a usable title, URL, or publication time with a reason.
- [x] Deduplicate exact canonical URLs within the collection window.
- [x] Deduplicate normalized titles within 48 hours.
- [x] Detect exact or near-exact content copies when text is available.
- [x] Add fixture checks for accepted, rejected, exact-duplicate, and syndicated-copy cases.

## Verification

Process the fixture collection twice. The Article output must be identical, contain stable IDs, and classify every fixture with an explicit status.

## Done when

Every task above is checked and the verification command passes.

Verification: `pytest tests/test_normalization.py` processes deterministic fixtures twice and covers accepted, rejected, URL/title duplicate, and syndicated-copy outcomes.
