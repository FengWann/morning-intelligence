# Personal AI Market Intelligence — Daily News MVP Specification

Status: Draft v0.2 — implementation baseline  
Date: 2026-09-12  
Scope: Daily News MVP only

## 1. Purpose

Build a personal morning intelligence brief that answers:

1. What important events happened?
2. Why do they matter?
3. What changed compared with the recent news cycle?

This release establishes the reliable news-to-brief pipeline needed by the future Opportunity Engine. It does not attempt to identify or validate commercial opportunities.

## 2. Product principles

- News is input, not output.
- Events, rather than individual articles, are the unit of analysis.
- Every factual statement in the brief must be traceable to source articles.
- Facts, analysis, and uncertainty must be distinguishable.
- Independent corroboration matters more than raw article count.
- A late, incomplete, or failed source must not invalidate the whole daily run.
- V1 favors a small reliable pipeline over speculative infrastructure.

## 3. Confirmed product decisions

| Decision | V1 choice |
|---|---|
| Brief language | Primarily Chinese; retain English names and important technical terms |
| Editorial allocation | Politics, Business, AI/Technology, and Singapore/Asia receive approximately equal attention |
| Target duration | 10–15 minutes when read aloud |
| Delivery time | Ready before 09:00 Asia/Singapore |
| Run calendar | Every calendar day, including weekends and Singapore public holidays |
| Audio | No generated MP3; iPhone Shortcut reads the published text using system speech |
| Operating cost | No spending beyond the user's existing ChatGPT Plus subscription |
| Analysis runtime | A scheduled Codex task on the user's computer |
| Host availability | The user's computer will be powered on and online from 08:00–09:00 Asia/Singapore |
| Public delivery | A sanitized static brief may be publicly hosted |
| Private data | Raw collection data, preferences, processing logs, and future opportunity data remain private |
| Repository | Code and sanitized public briefs share one public GitHub repository; private runtime data is excluded |
| Editorial stance | Fact-first and politically non-aligned; disputed claims are attributed and credible differing accounts are represented |
| External-service acceptance | GitHub Pages, Codex scheduling, iPhone Shortcut, and seven-day passage are verified with automated simulations; live activation is not required for automated completion |
| Event Registry | Not required in V1 |
| Opportunity Engine | Out of scope |

## 4. User experience

### 4.1 Daily flow

```text
08:00  Scheduled run starts
        Collect recent news
        Normalize and deduplicate articles
        Group articles into events
        Rank and select events
        Produce Chinese intelligence brief
        Validate citations and sanitize output
        Publish static files

09:00  iPhone Shortcut fetches latest.json
        Opens today's brief
        Reads the speech text aloud
```

The run should normally finish by 08:45, leaving 15 minutes for retries.

### 4.2 Brief structure

```text
Opening

Politics
Business
AI / Technology
Singapore / Asia

What Changed?
Things to Watch
Sources
```

Each category receives roughly equal editorial space. Equality is a target, not a hard quota: a category may be shorter when no sufficiently important event exists.

### 4.3 Event presentation

Each selected event contains:

- A concise Chinese headline
- What happened
- Why it matters
- What is new relative to previous reporting, when known
- Who or what is affected
- A confidence label
- Links to supporting sources

The spoken version omits raw URLs and citation mechanics but preserves source names and uncertainty.

## 5. Scope

### 5.1 In scope

- GDELT-based global discovery
- Direct RSS and official feeds
- Article normalization
- Exact and near-duplicate removal
- Cross-source event clustering
- Importance scoring
- Four-section daily brief
- Short recent-history comparison for “What Changed?”
- Markdown and machine-readable static output
- Daily archive
- Public sanitized publishing
- iPhone Shortcut-compatible delivery
- Retry behavior and visible run status

### 5.2 Out of scope

- Opportunity detection or scoring
- Problem Signal extraction
- Opportunity lifecycle management
- Market sizing, competitor research, or customer discovery
- PostgreSQL or a remote database
- Event Registry integration
- Generated MP3 files
- A custom mobile app
- A complex web dashboard
- User accounts or authentication
- Real-time alerts
- Full article redistribution
- Training or fine-tuning a model

## 6. Inputs

### 6.1 Discovery sources

GDELT is used for broad event discovery and geographic coverage. Direct feeds provide higher-quality evidence and authoritative source links.

Initial source groups:

- Global news: Reuters, AP, BBC
- Business: Financial Times, Bloomberg, CNBC and authoritative company announcements where feeds are available
- Singapore/Asia: CNA and Singapore government or regulator feeds
- AI/Technology: OpenAI, Google DeepMind, Anthropic, NVIDIA, Microsoft, MIT Technology Review and TechCrunch
- Policy and regulation: relevant government, regulator and standards-body feeds

Source availability must be verified during implementation. A missing or inaccessible feed is skipped and reported; it must not be replaced with scraping that violates publisher terms.

### 6.2 Collection window

- Primary window: previous 24 hours
- Recovery window after a failed run: previous 48 hours
- Recent comparison window: previous 7 completed daily runs

The pipeline stores a stable source identifier and canonical URL so reruns do not create duplicate articles.

## 7. Data model

V1 stores JSON files in a private workspace. A relational database is deferred until cross-day volume or query needs justify it.

### 7.1 Article

```json
{
  "id": "sha256-of-canonical-url",
  "title": "string",
  "source_id": "string",
  "source_name": "string",
  "url": "https://...",
  "canonical_url": "https://...",
  "published_at": "ISO-8601 timestamp",
  "collected_at": "ISO-8601 timestamp",
  "language": "BCP-47 language tag or null",
  "country": "ISO country code or null",
  "topics": ["string"],
  "feed_summary": "string or null",
  "text": "string or null",
  "content_hash": "sha256",
  "status": "accepted | duplicate | rejected",
  "rejection_reason": "string or null"
}
```

### 7.2 Event

```json
{
  "id": "stable generated identifier",
  "title": "string",
  "summary": "string",
  "first_seen_at": "ISO-8601 timestamp",
  "last_seen_at": "ISO-8601 timestamp",
  "article_ids": ["string"],
  "distinct_source_count": 0,
  "countries": ["ISO country code"],
  "topics": ["string"],
  "entities": ["string"],
  "importance": {
    "impact": 0,
    "breadth": 0,
    "novelty": 0,
    "momentum": 0,
    "source_quality": 0,
    "user_relevance": 0,
    "total": 0,
    "rationale": "string"
  },
  "confidence": "high | medium | low"
}
```

### 7.3 Daily run

```json
{
  "date": "YYYY-MM-DD",
  "timezone": "Asia/Singapore",
  "started_at": "ISO-8601 timestamp",
  "completed_at": "ISO-8601 timestamp or null",
  "status": "running | complete | partial | failed | missed",
  "source_results": [],
  "article_count": 0,
  "event_count": 0,
  "selected_event_ids": [],
  "warnings": []
}
```

## 8. Processing pipeline

### 8.1 Collect

1. Request GDELT results for the configured subject and geographic lanes.
2. Read configured direct feeds.
3. Preserve source URL, publication timestamp, title, supplied description and available metadata.
4. Retrieve article text only when permitted and necessary.
5. Record each source's success, failure and article count.

### 8.2 Normalize

- Convert timestamps to UTC while retaining the Singapore reporting date.
- Normalize whitespace and Unicode.
- Remove known tracking parameters from URLs.
- Resolve declared canonical URLs when available.
- Map source names to stable source IDs.
- Detect language.
- Reject entries without a usable title, URL or publication time.

### 8.3 Deduplicate

Deduplication proceeds from cheapest to most expensive:

1. Exact canonical URL match
2. Exact normalized-title match within 48 hours
3. Exact or near-exact content hash
4. Semantic and entity-aware event matching

Syndicated copies from the same source organization count as one independent source for corroboration.

### 8.4 Cluster into events

Candidate articles may join an existing event when all of the following support the match:

- They are within the configured event time window.
- Their titles or summaries describe the same occurrence, not merely the same topic.
- Important people, organizations and places are compatible.
- The claimed action or change is compatible.

Ambiguous cases remain separate. False merges damage factual accuracy more than additional small clusters damage presentation quality.

V1 may use Codex reasoning for semantic comparison rather than maintaining a separate embedding service. The pipeline must retain enough intermediate data to replace this with embeddings later without changing the Article and Event contracts.

### 8.5 Score importance

Each dimension is scored from 0 to 100:

```text
Importance =
  30% Impact
  20% Breadth
  15% Novelty
  15% Momentum
  10% Source Quality
  10% User Relevance
```

Definitions:

- Impact: probable real-world consequence and number of affected actors
- Breadth: local, Singapore, Asia or global reach
- Novelty: degree of genuinely new information
- Momentum: growth in independent reporting or development speed
- Source Quality: authority, directness and independent corroboration
- User Relevance: fit with the four currently equal interest lanes

Every score must include a short rationale. Scores rank candidates; they are not statements of truth.

### 8.6 Select events

- Build a candidate list for each editorial category.
- Prefer independently corroborated events.
- Avoid selecting the same event in multiple sections.
- Do not fill a section with weak events merely to satisfy equal allocation.
- Keep the final spoken text within the 10–15 minute target.
- Preserve at least one Singapore/Asia lens when sufficiently important evidence exists.

### 8.7 Produce “What Changed?”

V1 compares selected events and their entities/topics with the previous seven daily archives. It may report:

- A genuinely new development in an existing story
- A material increase in coverage across independent sources
- Expansion into another geography or industry
- A newly announced decision, policy, product or measured outcome

It must not call repeated reporting a trend. If there is insufficient history, the section says so and remains short.

### 8.8 Generate and verify the brief

The generation step receives only selected event records and their source evidence. It must:

- Write concise Chinese suitable for listening
- Keep named entities and important technical terms accurate
- Attribute contested claims
- Avoid unsupported causal statements
- State meaningful uncertainty
- Never invent a source or URL

Before publishing, a verification pass checks that every event has at least one accessible source URL and that claims do not exceed the supplied evidence.

### 8.9 Sanitize and publish

The public output must not contain:

- API keys, credentials or local file paths
- Processing prompts or internal logs
- User notes, feedback or private preferences
- Full copyrighted article text
- Future private opportunity analysis

Only brief text, event summaries, source names, source URLs and minimal publication metadata are published.

## 9. Storage and outputs

Private workspace:

```text
data/
  runs/YYYY-MM-DD/run.json
  articles/YYYY-MM-DD.json
  events/YYYY-MM-DD.json
  state.json
```

Public static output:

```text
public/
  index.html
  latest.json
  briefs/YYYY-MM-DD.md
  briefs/YYYY-MM-DD.json
```

`latest.json` is the stable iPhone entry point:

```json
{
  "date": "YYYY-MM-DD",
  "status": "complete | partial",
  "brief_url": "https://...",
  "speech_text": "string",
  "generated_at": "ISO-8601 timestamp"
}
```

The public Git history must never include private `data/` files. Publication should copy only an explicit allowlist from `public/`.

## 10. Scheduling and recovery

- Run once every calendar day at 08:00 Asia/Singapore through a Codex scheduled task, including weekends and Singapore public holidays.
- The task runs in the local project and requires the host computer to be on and online.
- If the scheduled run is missed because the host is off, asleep or offline, start a catch-up run when the host becomes available.
- Use the reporting date as the idempotency key so a catch-up cannot duplicate a completed daily run.
- After multiple missed days, generate only the current day's brief. Record earlier dates as `missed`; do not backfill stale morning briefs.
- A failed source is retried with bounded backoff.
- A failed full run retries once before 08:45.
- If some sources fail but sufficient evidence remains, publish with `partial` status and a short freshness warning.
- If the run cannot produce a valid brief, keep the previous successful public brief and update status metadata; never publish an empty or fabricated brief.
- Re-running the same reporting date must be idempotent.

## 11. iPhone Shortcut contract

At 09:00 Asia/Singapore, the Shortcut:

1. Fetches `latest.json`.
2. Confirms the date is today and status is `complete` or `partial`.
3. Reads `speech_text` using the iPhone system voice.
4. If the brief is stale or unavailable, announces a short failure message rather than reading yesterday's brief as current.

The Shortcut contains no API key or private database credential.

## 12. Reliability and quality requirements

### 12.1 Editorial integrity

- The system has no fixed political alignment.
- Confirmed facts, attributed claims and system analysis must be presented as distinct kinds of statements.
- A disputed political or geopolitical event requires at least two credible, meaningfully independent sources before it is presented without a single-source warning.
- Materially different credible accounts must be summarized fairly rather than collapsed into artificial certainty.
- Government, company, campaign and advocacy statements are treated as claims from interested parties unless independently verified.
- Source count alone does not establish truth; syndicated copies and reports derived from the same original claim count as one evidentiary chain.

### 12.2 Functional acceptance

V1 is accepted when it can:

- Complete seven consecutive scheduled daily runs without manual intervention
- Publish before 09:00 on at least six of those seven days
- Produce a 10–15 minute Chinese spoken brief
- Cover the four editorial categories without systematic source domination
- Avoid repeating the same real-world event as separate headline items
- Attach valid source evidence to every selected event
- Retain private daily Article, Event and Run archives
- Allow historical briefs to be opened by date
- Let an iPhone fetch and read the current brief without credentials

For unattended implementation, external integrations and passage of time are represented by deterministic simulations. The build must still produce activation-ready GitHub Pages, scheduler, and Shortcut instructions, but it does not require credentials, a physical iPhone, or seven elapsed days.

### 12.3 Editorial review sample

For the seven-day acceptance period, the user reviews each selected event as:

- Useful
- Already known
- Too generic
- Incorrectly clustered
- Not important
- Missing an important event

V1 does not automatically learn from this feedback. The review establishes the baseline for the later feedback system.

### 12.4 Safety checks

- No secret may appear in public output or logs committed to the public host.
- No brief may contain a factual event without a source link.
- Low-confidence or single-source claims must be labeled.
- A publisher's full article body must not be included in public output.

## 13. Implementation sequence

1. Define source configuration and verify reachable feeds.
2. Implement collection, normalization and exact deduplication.
3. Persist Article and Run archives.
4. Implement event clustering and Event persistence.
5. Implement scoring, selection and brief generation.
6. Implement evidence verification and sanitization.
7. Publish static output and `latest.json`.
8. Build and test the iPhone Shortcut.
9. Add the daily Codex schedule.
10. Run the seven-day acceptance period.

## 14. Deferred upgrade triggers

Add a component only when its trigger occurs:

| Deferred component | Trigger |
|---|---|
| Event Registry | Self-managed clustering quality remains unacceptable after measured tuning |
| Embedding service | Codex-based matching is too slow, inconsistent or consumes too much account usage |
| PostgreSQL + pgvector | JSON archives make cross-day queries or concurrent updates impractical |
| OpenAI API | Scheduled Codex usage is unreliable or the user accepts separate API billing |
| Generated MP3 | System speech is insufficient or durable audio distribution becomes necessary |
| Web dashboard | Archive navigation and static reports no longer support review needs |
| Opportunity Engine | Daily brief meets its seven-day reliability and editorial acceptance criteria |

## 15. Definition of done

The Daily News MVP is done when a scheduled run reliably turns fresh public news into an evidence-backed, sanitized Chinese brief, publishes it before 09:00, and an iPhone can read it aloud without any additional paid service or manual daily action.
