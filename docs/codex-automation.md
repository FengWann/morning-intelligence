# Daily Codex automation (activation-ready)

The live task uses the following values:

- Name: `Morning Intelligence Brief`
- Schedule: every day at 08:00, timezone `Asia/Singapore`
- Project directory: `C:\Users\admin\OneDrive - National University of Singapore\Desktop\NUS\SELF\News`
- Final validation command: `python -m news_intelligence run --catch-up`

Automation description:

> In the saved News project, generate the current Asia/Singapore day's Chinese
> intelligence brief using only free public sources and the existing ChatGPT
> Plus/Codex session. Follow `SPEC.md` and
> `docs/tasks/12-intelligence-synthesis.md`. Normalize, deduplicate, and cluster
> the previous 24 hours of reporting into Events, then synthesize Events into
> evidence-backed Intelligence Themes. Shared keywords alone never justify a
> theme. Compare private complete/partial archives across 7, 30, and 90 valid
> days; deduplicate evidentiary chains and never treat syndicated repetition as
> acceleration. Each theme must lead with a Chinese conclusion and include Event
> IDs, public source URLs, material change, impact mechanism, affected actors,
> problem signals, counter-evidence, uncertainty, confidence, and score rationale.
> Produce at most one Opportunity Hypothesis, only from an accepted problem
> signal; label assumptions and do not claim market size, pricing, willingness to
> pay, or validation. Validate the structured contract before publishing. Keep
> the previous valid brief when validation fails. Publish the full sanitized web
> brief and dated JSON, run `python -m news_intelligence run --catch-up`, commit
> only allowlisted public output, and push `main`. Read the Windows user
> `SERVERCHAN_SENDKEY` into the process without displaying it, then run
> `python -m news_intelligence send-wechat --brief
> public/briefs/YYYY-MM-DD.json --live-send` using today's Singapore date. Send
> no more than four substantive theme messages plus one change/opportunity
> summary; send fewer when evidence is weak, and rely on the state file to resume
> without duplicates. Use no separately billed API or paid service. On wake,
> catch up only the current Singapore date. Stay quiet on success and notify only
> on failure or required user action.

The host must be awake and online. Enable the scheduler's run-on-wake behavior so
the same task performs a current-day catch-up after downtime. The command validates
the prepared `public/latest.json`, applies the deterministic scheduling policy, and
returns a nonzero exit code when no valid current publication exists. Automated
tests simulate external delivery; they do not consume the daily ServerChan quota.
