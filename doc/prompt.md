# Autonomous Implementation Prompt

You are the main implementation agent for the Daily News MVP in this workspace. Complete the project autonomously from the existing specification and task files. Do not ask the user to write code, run commands, configure credentials, click through interfaces, wait seven days, or perform testing.

## Read first

Before changing anything, read completely:

1. `SPEC.md`
2. `progress.md`
3. Every file in `docs/tasks/`, in numeric order
4. `README.md`, `.gitignore`, `.env.example`, and the existing source tree
5. Any applicable `AGENTS.md`

Instruction priority is: system and user instructions, `SPEC.md`, this prompt, module task files, then README guidance.

Do not expand the product into full opportunity validation, PostgreSQL, Event
Registry, generated MP3, a custom mobile application, or a complex dashboard.
Module 12 explicitly permits one evidence-backed Opportunity Hypothesis, but not
market size, pricing, customer validation, or Opportunity lifecycle claims.

## Delegate every module

Act as the coordinating main Agent. For every module in `progress.md`:

1. Delegate the module to a child Agent. Give it the complete module task file, relevant specification sections, and current repository state.
2. Give one child Agent ownership of one module only.
3. Respect dependencies. Do not start a dependent module until its prerequisites pass. Independent modules may run in parallel when safe.
4. Require the child Agent to implement the module, write tests, run focused checks, and report its changes and verification results.
5. Inspect the resulting diff and rerun the relevant checks yourself. Never accept a child Agent's self-assessment without verification.
6. Fix integration problems directly or send a focused correction to the same child Agent.
7. Check a task box only after that exact behavior exists and is verified.
8. Check the module in `progress.md` only after every box in its task file is checked and all module verification passes.

Do not create Git commits unless the user explicitly asks. Preserve unrelated user changes.

## Work autonomously

- When a minor implementation detail is unspecified, choose the smallest reasonable design, document the assumption, and continue.
- Do not pause for optional preferences.
- Never fabricate a successful external action.
- Do not require GitHub credentials, an API key, a physical iPhone, a live Codex automation, or seven elapsed days.
- Use the deterministic simulations defined below while producing activation-ready configuration and instructions.
- If a genuine blocker remains after exhausting safe alternatives, record it precisely and continue every unblocked module. Never check a blocked task or module.

## Engineering requirements

Use Python and keep the architecture minimal. Prefer the standard library. Add a dependency only when it materially reduces risk or complexity. Reuse existing code before adding abstractions. Do not create speculative plugin systems or interfaces with only one implementation.

All production Python must:

- Have complete type annotations.
- Pass `mypy` with `strict = true`.
- Pass `ruff check`.
- Pass `ruff format --check`.
- Validate untrusted network and feed data at system boundaries.
- Keep secrets, private paths, prompts, logs, and article bodies out of public output.

Put tool configuration in the Python project configuration rather than scattering flags across scripts.

## Test requirements

Use `pytest` for all automated tests.

- Enforce at least 90% total line coverage.
- Enforce at least 90% branch coverage for normalization, deduplication, clustering, ranking, editorial verification, sanitization, run recovery, and Shortcut contract handling.
- Use deterministic fixtures for network responses, dates, model output, and external services.
- Default tests must not need live network access, paid APIs, GitHub credentials, a physical phone, or wall-clock waiting.
- Keep one optional live-ingestion smoke command separate from the default test suite.
- A module is not complete when tests are skipped because an external service is unavailable.

Before completing a module, run its focused tests plus strict `mypy`, `ruff check`, and `ruff format --check` for affected code. Before completing the project, run the entire suite with coverage enforcement and every quality gate.

## ChatGPT Plus constraint

The user accepts only the existing ChatGPT Plus subscription and no separately billed API usage. Do not add or require an OpenAI API key. Model-assisted reasoning in the live product is performed by the scheduled Codex task. Keep deterministic local fallbacks and fixture-driven tests so the repository can be verified without invoking a model.

## Simulate external integrations

### GitHub Pages

- Produce an activation-ready Pages workflow and static output structure.
- Simulate the Pages build locally.
- Verify the explicit public allowlist and fail closed if a secret, private path, prompt, log, or article body is detected.
- Do not push, publish, or request credentials.

### Codex scheduling

- Produce the exact activation-ready automation description and repository command.
- Simulate 08:00 daily runs, bounded retry, same-day idempotency, catch-up after host recovery, partial runs, failed runs, and multi-day downtime.
- Never claim that a live automation was created.

### iPhone Shortcut

- Document exact Shortcut construction and 09:00 personal automation steps.
- Implement a local simulator for the `latest.json` contract.
- Test complete, partial, stale-date, offline, and malformed-response behavior.
- Never claim physical-device testing occurred.

### Seven-day acceptance

- Use a controlled clock to simulate seven consecutive calendar days.
- Generate corresponding private run records and public output in a temporary test workspace.
- Verify that at least six of seven simulated briefs are ready before 09:00, every
  selected event has evidence, and stale output is never presented as current.
  The legacy Module 11 fixture may retain its spoken-length assertion, but Module
  12 has no spoken-duration acceptance requirement.
- Do not wait for real days to pass.

## Data and editorial rules

- Treat Event, not Article, as the editorial unit.
- Preserve evidence URLs for every selected event.
- Distinguish confirmed facts, attributed claims, and system analysis.
- For disputed political or geopolitical claims, require two credible independent sources or show a single-source warning.
- Do not count syndicated copies as independent corroboration.
- Keep allocation approximately balanced across Politics, Business, AI/Technology, and Singapore/Asia, but never include weak material only to fill a quota.
- Prefer false splits over false event merges when evidence is ambiguous.
- Never describe repeated coverage alone as a trend.
- Keep public output sanitized and private archives excluded from version control.

## Intelligence synthesis rules

For Module 12, Article and Event records remain evidence inputs; an Intelligence
Theme is the delivered unit. Read `docs/tasks/12-intelligence-synthesis.md`
completely before implementation and follow its contracts.

- Never deliver a list of rewritten article summaries as intelligence synthesis.
- Connect Events only when a stated causal, operational, market, regulatory, or
  technological mechanism is supported; shared keywords are not enough.
- A synthesis normally needs at least two distinct Events. Label a single-Event
  result as event analysis rather than implying a broader pattern.
- Compare available private history over 7, 30, and 90 days. Repetition and
  syndicated copies alone never establish continuation or acceleration.
- Lead every theme with a Chinese conclusion, then show evidence, material change,
  impact chain, affected actors, problem signals, counter-evidence, uncertainty,
  confidence, and source links.
- Every impact link, problem signal, and opportunity field must reference valid
  Event IDs. Reject unknown IDs and unsupported claims before rendering.
- Generate at most one Opportunity Hypothesis from an accepted problem signal.
  It must state current solution, gap, bounded AI leverage, possible buyer, key
  assumptions, confidence, and the next validation step.
- Preserve counter-evidence and alternative explanations. Do not turn plausible
  causality into confirmed fact.
- All analysis, summaries, and delivery text are Simplified Chinese. Source names,
  original titles, proper nouns, and necessary technical terms may remain in their
  original language.
- Render ServerChan messages from structured Intelligence Theme fields, never by
  splitting free-form prose. Send at most five messages: the three strongest
  material changes, a strong Singapore/Asia theme or next-best theme, and a final
  change summary plus Opportunity Radar. Never add weak filler.
- Retain the zero-additional-cost constraint: no separately billed API, OpenAI API
  key, paid host, or paid ServerChan tier.

## Module 12 completion additions

Before checking Module 12 or changing the live automation prompt:

- Achieve at least 90% line and branch coverage for synthesis, history comparison,
  evidence validation, and structured WeChat rendering.
- Exercise related and unrelated Events, syndicated copies, conflicting evidence,
  insufficient history, false acceleration, partial sources, fewer than five
  messages, no valid opportunity, invalid structured model output, and retry.
- Inspect one deterministic seven-day result and confirm that conclusions precede
  news evidence and that no unsupported trend or commercial claim appears.
- Update the live 08:00 automation only after the full `pytest`, strict `mypy`,
  `ruff check`, and `ruff format --check` gates pass.

## Progress discipline

The checklists represent verified repository state.

- Leave a box unchecked while any part is missing or unverified.
- Checking a box requires both implementation and repository evidence of verification.
- Keep `progress.md` synchronized with the module files.
- After each module, append a concise verification note to its task file with commands and results.
- Never weaken or delete a test to make a module pass.
- Never lower type, lint, format, or coverage standards.

## Completion gate

Do not stop after scaffolding or one successful happy path. Continue until every module is implemented and every automated gate passes.

The project is complete only when:

- Every task checkbox in every `docs/tasks/<module-name>.md` is checked.
- Every module checkbox in `progress.md` is checked.
- The complete `pytest` suite passes with the required line and branch coverage.
- Strict `mypy` passes.
- `ruff check` passes.
- `ruff format --check` passes.
- Public-output sanitization tests pass.
- The deterministic seven-day acceptance simulation passes.
- README documents clean-checkout setup, local smoke run, testing, simulated external integrations, and manual activation.

In the final report, lead with the implemented outcome, list exact verification commands and results, disclose that external services were simulated rather than activated, and identify every remaining unchecked item. Never call the project complete while an item remains unchecked.
