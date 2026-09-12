# Module 11 — Seven-Day Acceptance

## Outcome

The Daily News MVP demonstrates that it can operate reliably and produce useful, evidence-backed briefs for seven consecutive calendar days.

## Dependencies

- Module 09 — Scheduling and Recovery
- Module 10 — iPhone Shortcut Delivery

## Tasks

- [x] Simulate a seven-consecutive-day acceptance window with controlled clocks and fixtures.
- [x] Record whether each simulated brief was published before 09:00.
- [x] Confirm at least six of seven briefs were published before 09:00.
- [x] Confirm every selected event has valid source evidence.
- [x] Confirm each brief fits the 10–15 minute spoken target.
- [x] Review category balance and source domination.
- [x] Label each selected event as Useful, Already known, Too generic, Incorrectly clustered, or Not important.
- [x] Record important events the system missed.
- [x] Fix any security, fabrication, duplicate-event, or stale-brief defect and restart the acceptance window.
- [x] Summarize measured results and remaining editorial weaknesses.

## Verification

Run the deterministic seven-day simulation and review its dated records, public briefs, Shortcut outcomes, and editorial labels. No real-time waiting, credentials, or physical device is required.

## Done when

Every task above is checked and the simulated seven-day evidence is linked from this file.

## Verification record

- Integrated simulation: `src/news_intelligence/acceptance.py`
- Automated acceptance: `tests/test_acceptance.py`
- Dated measured evidence and limitations: [`docs/acceptance-simulation.md`](../acceptance-simulation.md)
- Clean-checkout setup, full gates, simulated integrations, and manual activation:
  [`README.md`](../../README.md)
- Result: 6/7 before 09:00; seven 627-second briefs; four balanced categories;
  largest daily source share 33.3%; all selected events evidence-backed.
- The deliberately late day announced unavailable at 09:00 instead of presenting
  stale output. No security, fabrication, duplicate-event, or stale-brief defect was
  found, so a restarted acceptance window was not required.
- Full suite: `python -m pytest -q` — 77 passed, 97.26% total coverage.
- Types: `python -m mypy src tests` — passed in strict mode.
- Lint: `python -m ruff check src tests` — passed.
- Format: `python -m ruff format --check src tests` — passed.
