# Personal AI Market Intelligence

Daily News MVP implementation workspace.

- Product specification: [`SPEC.md`](SPEC.md)
- Module progress: [`progress.md`](progress.md)
- Executable task definitions: [`docs/tasks/`](docs/tasks/)
- Autonomous main-Agent prompt: [`doc/prompt.md`](doc/prompt.md)

Implementation proceeds in the order listed in `progress.md`. A module is complete only when every checkbox in its task file is complete and its verification command passes.

## Install

Python 3.12 or newer is required. From a clean checkout, create and activate a
virtual environment, then install the project and development checks:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Runtime settings are optional environment variables documented in
`.env.example`; the application does not read or require a committed `.env`
file. Private data defaults to `data/`, while publishable files default to
`public/`.

## Foundation smoke check

This command requires neither network access nor credentials:

```powershell
news_intelligence --help
```

The equivalent command without relying on the installed console-script path is
`python -m news_intelligence --help`.

## Local smoke run

The deterministic checks below are the default smoke run and require no network,
credentials, paid API, GitHub account, physical iPhone, or wall-clock waiting:

```powershell
python -m pytest tests/test_acceptance.py -q --no-cov
```

An optional live collection can be run separately. It reads the starter source
configuration and reports inaccessible sources without aborting the collection:

```powershell
python -m news_intelligence collect --live --sources config/sources.example.json
```

## Development checks

Run every repository gate before treating a change as complete:

```powershell
python -m pytest -q
python -m mypy src tests
python -m ruff check src tests
python -m ruff format --check src tests
```

Pytest enforces at least 90% total line coverage with branch measurement enabled;
strict mypy and both Ruff lint and format checks are configured in `pyproject.toml`.

## Simulated external integrations

Automated completion does not create external accounts or claim live activation:

- `tests/test_publishing.py` locally builds and scans the explicit public
  allowlist used by the Pages artifact.
- `tests/test_scheduling.py` controls the clock to test retries, idempotency,
  catch-up, missed dates, and failure preservation.
- `tests/test_shortcut.py` models complete, partial, stale, offline, and malformed
  `latest.json` responses.
- `tests/test_acceptance.py` runs the real pipeline across seven controlled days in
  a temporary workspace. Its measured result and limitations are recorded in
  [`docs/acceptance-simulation.md`](docs/acceptance-simulation.md).

These simulations validate mechanics. Real feed availability, editorial usefulness,
source mix, and missed-event review still require observation after live activation.

## Manual activation

### GitHub Pages

The activation-ready [`.github/workflows/pages.yml`](.github/workflows/pages.yml)
validates the public allowlist, uploads only `public/`, and deploys it with the
standard GitHub Pages action. After pushing the repository, enable GitHub Pages with
**GitHub Actions** as the source. Deployment runs only after validation passes. No
application secret or private `data/` file belongs in the workflow or Pages artifact.

### Codex scheduler

Use the exact schedule and task text in
[`docs/codex-automation.md`](docs/codex-automation.md). The saved task runs every day
at 08:00 Asia/Singapore and finishes with:

```powershell
python -m news_intelligence run --catch-up
```

The computer must be awake and online, with run-on-wake enabled for current-day
catch-up. This repository provides and tests the schedule policy but does not create
the live Codex automation.

## iPhone Shortcut delivery

Replace `LATEST_JSON_URL` below with the public HTTPS URL ending in
`/latest.json`. Create a Shortcut named **Morning Intelligence Brief** with
these actions, in this exact order:

1. **URL** — `LATEST_JSON_URL`.
2. **Get Contents of URL** — method `GET`; no headers, authentication, or body.
3. **Get Dictionary from Input** using the response. Put actions 2–3 inside a
   **Try** block if that option is available on the installed iOS version.
4. **Current Date**, then **Format Date** with custom format `yyyy-MM-dd` and
   time zone `Singapore`.
5. Read dictionary values `date`, `status`, and `speech_text` into variables.
6. **If** `date` equals the formatted current date **and** (`status` equals
   `complete` **or** `status` equals `partial`) **and** `speech_text` has a
   value, use **Speak Text** on `speech_text` with the preferred system voice.
7. **Otherwise**, use **Speak Text** on
   `今天的简报尚未准备好，请稍后再试。`. The Try error path, when available,
   must run this same action.

The date comparison must use Singapore time even while travelling. Never add
an API key: `latest.json` is intentionally public and read-only. Before
automation, run the Shortcut manually once, allow network access if prompted,
and verify it speaks either today's brief or the unavailable message.

### 09:00 personal automation

In Shortcuts, open **Automation**, create **Time of Day**, choose `09:00`,
**Daily**, and **Run Immediately**. Add **Run Shortcut**, select **Morning
Intelligence Brief**, disable run notifications if desired, and save. This is
a personal automation and is not shared through the repository.

### Recovery

- If the unavailable message plays, open the public `latest.json` URL in
  Safari. A missing page or network error means retry after connectivity or
  publication recovers.
- If the JSON opens but its `date` is not today's Singapore date, wait for the
  scheduled catch-up run; the Shortcut deliberately refuses stale briefs.
- If today's valid JSON opens but speech does not start, run the Shortcut
  manually, confirm volume/focus settings, and reselect the system voice.
- After changing the Pages address, update only the first **URL** action.

The automated equivalent of these branches is `tests/test_shortcut.py`; it
covers complete, partial, stale, offline, and malformed responses without a
physical phone or live credentials.

## Personal WeChat delivery

Preview the five ServerChan messages without credentials or network access:

```powershell
python -m news_intelligence send-wechat --brief public/briefs/2026-09-12.json
```

For an intentional live send, set `SERVERCHAN_SENDKEY` in the local environment
and add `--live-send`. The key is never written to files or output. Successful
message progress is stored in `data/wechat-state.json`, so rerunning the same
reporting date sends nothing twice and an interrupted run resumes at the next
message.
