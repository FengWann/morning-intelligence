# Module 12 — Intelligence Synthesis

## Outcome

Daily output is no longer a set of article or event summaries. The system turns
verified Events and recent history into a small set of evidence-backed Chinese
intelligence themes that explain what changed, why it matters, who is affected,
which problem appeared, and whether an AI opportunity is worth investigating.

News remains evidence. An Intelligence Theme is the unit delivered to the user.

## Dependencies

- Module 05 — Event Clustering
- Module 06 — Importance Ranking and Selection
- Module 07 — Brief Generation and Editorial Verification
- Module 08 — Static Publishing
- Personal WeChat delivery in `news_intelligence.wechat`

## Scope boundary

This module may produce an **Opportunity Hypothesis** supported by observed
problems. It must not claim product-market fit, willingness to pay, market size,
pricing, or validation without separate evidence. Competitor research, customer
interviews, and the full Opportunity lifecycle remain deferred.

## Data contracts

### Intelligence Theme

```json
{
  "id": "stable theme identifier",
  "reporting_date": "YYYY-MM-DD",
  "title_zh": "Chinese conclusion, not an article headline",
  "thesis_zh": "the synthesized judgment",
  "lanes": ["politics", "business"],
  "event_ids": ["event-id"],
  "evidence": [
    {"event_id": "event-id", "source_name": "source", "url": "https://..."}
  ],
  "change_state": "new | continuing | accelerating | turning | unchanged | insufficient_history",
  "change_summary_zh": "what materially changed",
  "impact_chain": [
    {
      "cause_zh": "observed change",
      "mechanism_zh": "how the effect propagates",
      "affected_actors_zh": ["actor"],
      "effect_zh": "probable consequence",
      "confidence": "high | medium | low",
      "evidence_event_ids": ["event-id"]
    }
  ],
  "problem_signals": [
    {
      "problem_zh": "observed or carefully inferred problem",
      "who_has_it_zh": ["actor"],
      "type": "regulatory | cost | labor | technology | operational | consumer | market",
      "evidence_event_ids": ["event-id"]
    }
  ],
  "counter_evidence_zh": ["evidence or condition that weakens the thesis"],
  "uncertainties_zh": ["unknown or assumption"],
  "confidence": "high | medium | low",
  "score": 0,
  "score_rationale_zh": "short explanation"
}
```

### Opportunity Hypothesis

```json
{
  "problem_zh": "specific problem already represented by a problem signal",
  "who_has_it_zh": ["user or organization"],
  "current_solution_zh": "observable current workflow or alternative",
  "gap_zh": "why that workflow may be insufficient",
  "ai_leverage_zh": "specific capability and its bounded role",
  "potential_product_zh": "testable product hypothesis",
  "potential_buyer_zh": ["buyer"],
  "evidence_event_ids": ["event-id"],
  "key_assumptions_zh": ["unverified assumption"],
  "next_validation_step_zh": "smallest evidence-gathering action",
  "confidence": "high | medium | low"
}
```

The dated public JSON adds `intelligence_themes` and an optional
`opportunity_hypothesis`. Raw article bodies, prompts, private history, and
user credentials remain prohibited from public output.

## Synthesis pipeline

```text
Articles
  -> Events
  -> related-event candidates
  -> Intelligence Themes
  -> 7/30/90-day comparison
  -> impact chains and problem signals
  -> optional Opportunity Hypothesis
  -> evidence validation
  -> Chinese web brief and five WeChat messages
```

### Theme construction rules

- Join Events only when a defensible mechanism connects them; shared keywords
  or broad topics are insufficient.
- A synthesized theme normally contains at least two distinct Events. A single
  Event may remain as event analysis but must be labelled as such.
- Preserve every source Event ID used by a conclusion, impact link, problem
  signal, and opportunity field.
- Derive a stable cross-day theme identity from normalized principal entities,
  affected actors, geography, and mechanism; do not derive it from the first
  article or today's wording. Ambiguous matches start a new theme.
- Prefer a narrower theme over a broad but weak narrative.
- Keep credible conflicting evidence and alternative explanations visible.
- Codex may propose relationships, but deterministic validation rejects unknown
  Event IDs, missing evidence, unsupported opportunity fields, and invalid
  confidence or change-state values.

### Longitudinal comparison rules

- Compare current themes with private archives covering 7, 30, and 90 valid
  `complete` or `partial` reporting days; ignore failed, missed, and running days,
  and use all valid history when fewer days exist.
- `new` means the theme or mechanism has not appeared in available history.
- `continuing` requires a material new development, not repeated coverage.
- `accelerating` requires a new development plus measurable growth in at least
  one of: independent evidentiary chains, geographic spread, industry spread,
  affected actors, or event frequency across comparison windows.
- `turning` requires evidence of a directional change such as a policy reversal,
  operational response, adoption decision, or changed outcome.
- `unchanged` themes are normally omitted from WeChat unless their continuing
  impact is exceptionally important.
- Use `insufficient_history` when the archive cannot support a defensible claim.
- Never treat raw article count or syndicated repetition as trend evidence.
- Deduplicate evidentiary chains before measuring frequency, momentum,
  acceleration, geographic spread, or industry spread.

### Theme scoring

Score from 0 to 100:

```text
Theme Score =
  25% Material Change
  25% Expected Impact
  20% Evidence Strength
  15% User Relevance
  10% Cross-domain or Geographic Breadth
   5% Novelty
```

Apply an explicit penalty for a single evidentiary chain, unresolved conflict,
or a thesis dominated by inference. Scores rank review priority; they do not
establish truth.

## Chinese output contract

The web brief is a coherent analysis organized around Intelligence Themes, not
four lists of headlines. Each displayed theme contains:

1. `核心判断`
2. `支撑事件与来源`
3. `与过去相比发生了什么变化`
4. `影响链`
5. `谁会受到影响`
6. `问题信号`
7. `不确定性与反证`

ServerChan remains limited to five free messages per day. Generate:

1. Highest-scoring material change
2. Second-highest material change
3. Third-highest material change
4. Singapore/Asia theme when strong enough; otherwise the next theme
5. `变化总结 + 机会雷达`

Each theme message begins with the conclusion and then gives evidence, change,
impact chain, uncertainty, and source links. It is not one message per article.
All analysis and summaries use Simplified Chinese; source names, original titles,
proper nouns, and important technical terms may retain their original language.

## Failure and degradation

- If one source fails, continue only when remaining Events support valid themes
  and label the run `partial`.
- If history is unavailable, use `insufficient_history`; do not fabricate a trend.
- If no cross-event relationship passes validation, send narrower event analyses
  rather than inventing a theme.
- If no problem has adequate evidence, omit Opportunity Radar and say evidence is
  insufficient.
- If fewer than four themes pass the quality threshold, send fewer substantive
  themes and do not use weak filler.
- Preserve the previous valid public brief if synthesis or evidence validation
  fails.
- WeChat retries resume from the first unsent message and never exceed five daily
  messages or resend a completed date.

## Minimal executable tasks

### Step 1 — Contracts and validation

- [x] Add typed `IntelligenceTheme`, `ImpactLink`, `ProblemSignal`, and
  `OpportunityHypothesis` models.
- [x] Validate enum values, score range, stable IDs, non-empty Chinese conclusions,
  reporting date, evidence URLs, and referenced Event IDs.
- [x] Reject claims, impact links, problem signals, and opportunity fields without
  evidence.

### Step 2 — Related-event synthesis

- [x] Build deterministic candidate groups from shared entities, affected actors,
  geography, time, and compatible causal mechanisms.
- [x] Keep keyword-only and ambiguous relationships separate.
- [x] Allow injected Codex output only through the validated structured contract.
- [x] Produce a labelled single-event analysis when no valid synthesis exists.

### Step 3 — Historical comparison

- [x] Read 7/30/90-day Event and theme history without publishing private archives.
- [x] Match themes across days using stable semantic identity rather than the first
  article ID or exact daily wording.
- [x] Classify `new`, `continuing`, `accelerating`, `turning`, `unchanged`, or
  `insufficient_history` using the rules above.
- [x] Demonstrate that syndicated or repeated coverage alone cannot produce
  `accelerating`.

### Step 4 — Impact and problem analysis

- [x] Generate evidence-linked impact chains with explicit mechanisms and affected
  actors.
- [x] Extract typed problem signals without presenting inference as observation.
- [x] Preserve counter-evidence, alternative explanations, and uncertainty.

### Step 5 — Opportunity hypothesis

- [x] Create at most one daily hypothesis from an accepted problem signal.
- [x] Include current solution, gap, bounded AI leverage, buyer, assumptions,
  evidence, confidence, and next validation step.
- [x] Reject market-size, pricing, willingness-to-pay, or validation claims that
  have no supplied evidence.

### Step 6 — Ranking and delivery

- [x] Implement the Theme Score and evidence penalties with a rationale.
- [x] Select the top three changes plus a strong Singapore/Asia theme when
  available, without duplicates or weak filler.
- [x] Render the web brief and at most five Chinese ServerChan messages from the
  structured fields rather than parsing prose headings.
- [x] Preserve working same-date WeChat idempotency and interrupted-run recovery.

### Step 7 — Publishing and automation

- [x] Extend the dated public JSON with sanitized themes and the optional hypothesis.
- [x] Extend the explicit public allowlist scanner tests to cover new fields.
- [x] Update the daily Codex task prompt only after the implementation passes all
  automated gates.
- [x] Keep the existing no-paid-API and environment-only SendKey constraints.

### Step 8 — Automated acceptance

- [x] Add deterministic multi-source fixtures containing related events, unrelated
  same-topic events, syndicated copies, contradictory evidence, and weak signals.
- [x] Test 7/30/90-day state classification and false-trend prevention.
- [x] Test every output claim has valid Event and source evidence.
- [x] Test fewer-than-five output, missing-history, partial-source, no-opportunity,
  invalid-model-output, and retry cases.
- [x] Confirm all delivered explanatory text is Chinese except permitted names,
  original titles, and technical terms.
- [x] Achieve at least 90% line and branch coverage for synthesis, longitudinal
  analysis, evidence validation, and structured WeChat rendering.
- [x] Pass the complete `pytest`, strict `mypy`, `ruff check`, and
  `ruff format --check` gates.

## Verification

Run focused synthesis, history, publishing, and WeChat tests. Then run:

```powershell
python -m pytest -q
python -m mypy src tests
python -m ruff check src tests
python -m ruff format --check src tests
```

Inspect one deterministic seven-day output and confirm that it leads with
conclusions, supports every claim with Events and URLs, labels uncertainty, and
does not convert repeated reporting into a trend.

Verified on 2026-09-12: 107 tests passed; total line/branch coverage was 95.90%,
with synthesis at 93% and structured WeChat rendering at 92%. Strict mypy, Ruff
lint, Ruff formatting, and `git diff --check` all passed. The deterministic
Module 12 acceptance fixture confirmed conclusion-first Chinese output, Event and
URL evidence, false-trend prevention, and no weak-message filler.

## Done when

Every task above is checked, focused branch coverage is at least 90%, all project
gates pass, the public schema contains no private data, and the Chinese WeChat
messages represent synthesized changes rather than selected articles.
