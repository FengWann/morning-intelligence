# Daily Codex automation (activation-ready)

This repository does not create or activate a live automation. When ready, create a
Codex scheduled task with the following values:

- Name: `Morning Intelligence Brief`
- Schedule: every day at 08:00, timezone `Asia/Singapore`
- Project directory: `C:\Users\admin\OneDrive - National University of Singapore\Desktop\NUS\SELF\News`
- Command: `python -m news_intelligence run --catch-up`

Automation description:

> In the saved News project, generate and verify today's brief using `SPEC.md` and
> the implemented collection-to-publication modules. Do not publish unless the
> evidence and sanitization checks pass. Then run
> `python -m news_intelligence run --catch-up` to apply recovery, idempotency, and
> run-status policy. Generate only the current Asia/Singapore reporting date. Never
> replace a valid public brief with failed output, and record older absent dates as
> missed. Report failures without exposing private data or credentials.

The host must be awake and online. Enable the scheduler's run-on-wake behavior so
the same task performs a current-day catch-up after downtime. The command validates
the prepared `public/latest.json`, applies the deterministic scheduling policy, and
returns a nonzero exit code when no valid current publication exists. Live activation
is deliberately outside automated tests.
