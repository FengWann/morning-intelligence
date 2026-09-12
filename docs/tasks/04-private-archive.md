# Module 04 — Private Archive and Run State

## Outcome

Each execution safely records its articles and run state without publishing private data.

## Dependencies

- Module 03 — Normalization and Deduplication

## Tasks

- [x] Implement the Daily Run schema from `SPEC.md`, including `missed` status.
- [x] Write normalized articles to the dated private archive.
- [x] Write run metadata using an atomic replace so interruption cannot corrupt the last valid file.
- [x] Use the Singapore reporting date as the idempotency key.
- [x] Make a repeated run reuse or update the same date rather than create duplicates.
- [x] Record source warnings without exposing secrets.
- [x] Confirm `data/` is excluded from version control.
- [x] Add a check for interrupted write recovery and same-day rerun behavior.

## Verification

Run the fixture pipeline twice for the same date and once with a simulated interrupted write. Only one valid archive for that date may remain.

## Done when

Every task above is checked and the verification command passes.

Verification: `pytest` (30 passed, 96.11% total coverage); `mypy src tests`;
`ruff check .`; and `ruff format --check .` all pass.
