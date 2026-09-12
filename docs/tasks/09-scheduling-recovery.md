# Module 09 — Scheduling and Recovery

## Outcome

The local Codex task runs every calendar day, retries safely, and catches up only the current date after downtime.

## Dependencies

- Module 08 — Static Publishing

## Tasks

- [x] Add the activation-ready definition and instructions for a daily 08:00 Asia/Singapore Codex automation without creating a live automation.
- [x] Verify in simulation that the automation targets this project directory.
- [x] Add bounded retry behavior for source failures.
- [x] Retry one failed full run before 08:45 when the host remains available.
- [x] Start a current-day catch-up when the host returns after a missed run.
- [x] Record older absent dates as `missed` without generating stale briefs.
- [x] Publish `partial` only when enough verified evidence remains.
- [x] Preserve the previous valid public brief when a run fails.
- [x] Prevent overlapping or duplicate runs for the same Singapore reporting date.
- [x] Exercise complete, partial, failed, same-day rerun, and multi-day-offline scenarios.

## Verification

Run the scenario checks with controlled dates. Each scenario must produce the expected run status and must never duplicate, erase, or replace the last valid brief with invalid output.

## Done when

Every task above is checked and the verification command passes.

## Verification note

- `python -m pytest` — 75 passed, 96.81% total line/branch coverage.
- `python -m mypy src tests` — passed with strict project configuration.
- `python -m ruff check src tests` — passed.
- `python -m ruff format --check src tests` — passed.
- `python -m news_intelligence run --catch-up` is implemented and covered by deterministic CLI tests for current, partial, stale, absent, invalid, and missing-flag behavior.
- Live Codex automation was intentionally not created; `docs/codex-automation.md` contains the activation-ready schedule, project target, command, and prompt.
