# Seven-Day Acceptance Simulation

The deterministic acceptance test uses a controlled Asia/Singapore clock and a
temporary workspace. It exercises normalization, deduplication, event clustering,
ranking, balanced selection, evidence-bound brief generation, private archives,
static publication, scheduling, and the Shortcut contract without network access.

## Measured result

| Date | Generated | Before 09:00 | Spoken seconds | 09:00 Shortcut |
|---|---:|:---:|---:|---|
| 2026-09-01 | 08:35 | Yes | 627 | Speak brief |
| 2026-09-02 | 08:35 | Yes | 627 | Speak brief |
| 2026-09-03 | 08:35 | Yes | 627 | Speak brief |
| 2026-09-04 | 09:05 | No | 627 | Announce unavailable |
| 2026-09-05 | 08:35 | Yes | 627 | Speak brief |
| 2026-09-06 | 08:35 | Yes | 627 | Speak brief |
| 2026-09-07 | 08:35 | Yes | 627 | Speak brief |

- Result: passed, with six of seven briefs ready before 09:00.
- Every day selected one Politics, Business, AI/Technology, and Singapore/Asia
  event; weak quota-filling was not needed by the controlled fixtures.
- Every selected event had at least one valid HTTPS evidence URL.
- Four source organizations were represented daily; the largest share was 33.3%.
- Every selected event was recorded with the baseline review label `Useful`.
- Important missed events were explicitly recorded as an empty list for every day.
- Private Article, Event, Run, and acceptance records and seven dated public briefs
  were created in the temporary workspace.
- No security, fabrication, duplicate-event, or stale-brief defect was found by the
  simulation and full regression suite, so the acceptance window did not restart.

## Remaining editorial weakness

Controlled fixtures validate mechanics, not real-world editorial judgment. Live
source availability, source mix, usefulness labels, and missed-event review still
need observation after activation; this does not require a physical device or seven
elapsed days for repository acceptance.

The scheduler currently owns only policy and writes a minimal terminal status record;
the acceptance orchestrator therefore re-archives the full `DailyRun` after that
decision. A future production collection command should preserve this ordering when
it replaces the current prepared-output CLI seam.

## Reproduce

```powershell
python -m pytest tests/test_acceptance.py -q --no-cov
python -m pytest -q
python -m mypy src tests
python -m ruff check src tests
python -m ruff format --check src tests
```
