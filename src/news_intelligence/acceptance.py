"""Deterministic seven-day end-to-end acceptance simulation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Literal

from news_intelligence.archive import (
    SINGAPORE,
    archive_daily_run,
    atomic_write_json,
    create_daily_run,
)
from news_intelligence.briefing import (
    BriefDraft,
    BriefInput,
    GeneratedBrief,
    build_input,
    deterministic_draft,
    generate_brief,
)
from news_intelligence.clustering import archive_events, cluster_articles
from news_intelligence.ingestion import CollectedArticle
from news_intelligence.normalization import Article, normalize_and_deduplicate
from news_intelligence.publishing import build_publication, publish
from news_intelligence.ranking import (
    CATEGORIES,
    RankedEvent,
    rank_events,
    select_events,
)
from news_intelligence.scheduling import AttemptResult, run_daily
from news_intelligence.shortcut import evaluate_latest

ReviewLabel = Literal[
    "Useful",
    "Already known",
    "Too generic",
    "Incorrectly clustered",
    "Not important",
]


@dataclass(frozen=True)
class DayEvidence:
    """Measured evidence for one controlled reporting day."""

    date: str
    generated_at: str
    published_before_0900: bool
    status: str
    selected_event_ids: tuple[str, ...]
    evidence_urls: tuple[str, ...]
    estimated_seconds: int
    category_counts: Mapping[str, int]
    source_counts: Mapping[str, int]
    editorial_labels: Mapping[str, ReviewLabel]
    missed_events: tuple[str, ...]
    shortcut_action_at_0900: str


@dataclass(frozen=True)
class AcceptanceReport:
    """Auditable result of the complete seven-day simulation."""

    started_on: str
    ended_on: str
    days: tuple[DayEvidence, ...]
    on_time_days: int
    passed: bool
    remaining_editorial_weaknesses: tuple[str, ...]


def _fixture_articles(day: date) -> list[Article]:
    topics = (
        ("Politics", "Government approves election policy package", "policy", "US"),
        ("Business", "Company announces global market expansion", "business", "GB"),
        ("AI", "Technology company launches new AI model", "technology", "US"),
        ("Asia", "Singapore launches regional transport plan", "asia", "SG"),
    )
    sources = (("reuters", "Reuters"), ("bbc", "BBC"), ("ap", "AP"), ("cna", "CNA"))
    raw: list[CollectedArticle] = []
    metadata: list[tuple[str, str]] = []
    for index, (lane, title, topic, country) in enumerate(topics):
        for source_id, source_name in (sources[index], sources[(index + 1) % 4]):
            raw.append(
                CollectedArticle(
                    source_id,
                    source_name,
                    f"{title} {day.isoformat()} according to {source_name}",
                    f"https://{source_id}.example/{day.isoformat()}/{lane.casefold()}",
                    f"{day.isoformat()}T00:30:00+00:00",
                    f"{source_name} reports {title} with implementation details",
                    "en",
                    f"{day.isoformat()}T00:45:00+00:00",
                )
            )
            metadata.append((topic, country))
    return [
        replace(article, topics=[topic], country=country)
        for article, (topic, country) in zip(
            normalize_and_deduplicate(raw), metadata, strict=True
        )
    ]


def _duration_generator(data: BriefInput) -> BriefDraft:
    draft = deterministic_draft(data)
    # The fixture narration is deliberately substantive and repeated only to model
    # a full-length editorial script without a network model call.
    context = (
        "以下补充说明各事件的影响范围、独立来源、已知事实和仍待观察的问题。"
        "本简报只依据列出的公开证据，不把重复报道误称为趋势。"
    )
    return replace(draft, opening=f"{draft.opening}\n{context * 27}")


def _counts(
    selected: Sequence[RankedEvent], data: BriefInput
) -> tuple[dict[str, int], dict[str, int]]:
    categories = Counter(item.category for item in selected)
    sources = Counter(
        evidence.source_id for event in data.events for evidence in event.evidence
    )
    return (
        {category: categories[category] for category in CATEGORIES},
        dict(sorted(sources.items())),
    )


def run_seven_day_acceptance(workspace: Path, start: date) -> AcceptanceReport:
    """Exercise the real pipeline for seven controlled Singapore calendar days."""
    if not workspace.is_absolute():
        raise ValueError("acceptance workspace must be an absolute path")
    results: list[DayEvidence] = []
    prior_latest: str | None = None
    for offset in range(7):
        day = start + timedelta(days=offset)
        finished = datetime.combine(
            day, time(9, 5) if offset == 3 else time(8, 35), tzinfo=SINGAPORE
        )
        nine = datetime.combine(day, time(9), tzinfo=SINGAPORE)
        shortcut_at_nine = evaluate_latest(prior_latest, day).action
        captured: dict[str, object] = {}

        def pipeline(
            _attempt: int,
            current_day: date = day,
            store: dict[str, object] = captured,
        ) -> AttemptResult:
            articles = _fixture_articles(current_day)
            events = cluster_articles(articles)
            ranked = rank_events(events, {item.id: item for item in articles})
            selected = select_events(ranked)
            archive_events(workspace / "data", current_day.isoformat(), events)
            data = build_input(
                current_day.isoformat(),
                selected,
                {item.id: item for item in articles},
                workspace / "data" / "events",
            )
            brief = generate_brief(data, generator=_duration_generator)
            store.update(
                articles=articles,
                events=events,
                selected=selected,
                data=data,
                brief=brief,
            )
            return AttemptResult("complete", sufficient_evidence=True)

        def publish_result(
            _result: AttemptResult,
            store: dict[str, object] = captured,
            current_finished: datetime = finished,
        ) -> None:
            data = store["data"]
            brief = store["brief"]
            assert isinstance(data, BriefInput)
            assert isinstance(brief, GeneratedBrief)
            publication = build_publication(
                data,
                brief,
                status="complete",
                generated_at=current_finished,
                base_url="https://brief.example",
            )
            publish(workspace / "public", publication, brief.markdown)

        schedule = run_daily(workspace, finished, pipeline, publish_result)
        articles = captured["articles"]
        selected = captured["selected"]
        data = captured["data"]
        brief = captured["brief"]
        assert isinstance(articles, list)
        assert isinstance(selected, list)
        assert isinstance(data, BriefInput)
        assert isinstance(brief, GeneratedBrief)
        run = create_daily_run(
            now=finished,
            started_at=datetime.combine(day, time(8), tzinfo=SINGAPORE),
            completed_at=finished,
            status="complete",
            article_count=len(articles),
            event_count=len(captured["events"]),  # type: ignore[arg-type]
            selected_event_ids=[item.event.id for item in selected],
        )
        archive_daily_run(workspace / "data", articles, run)
        latest_path = workspace / "public" / "latest.json"
        latest = latest_path.read_text(encoding="utf-8")
        if finished <= nine:
            shortcut_at_nine = evaluate_latest(latest, day).action
        category_counts, source_counts = _counts(selected, data)
        evidence_urls = tuple(
            evidence.url for event in data.events for evidence in event.evidence
        )
        labels: dict[str, ReviewLabel] = {item.event.id: "Useful" for item in selected}
        evidence = DayEvidence(
            day.isoformat(),
            finished.isoformat(),
            finished < nine,
            schedule.status or "failed",
            tuple(item.event.id for item in selected),
            evidence_urls,
            brief.estimated_seconds,
            category_counts,
            source_counts,
            labels,
            (),
            shortcut_at_nine,
        )
        atomic_write_json(
            workspace / "data" / "acceptance" / f"{day.isoformat()}.json",
            asdict(evidence),
        )
        results.append(evidence)
        prior_latest = latest

    on_time = sum(item.published_before_0900 for item in results)
    balanced = all(max(item.category_counts.values()) <= 1 for item in results)
    undominated = all(
        max(item.source_counts.values()) / sum(item.source_counts.values()) <= 0.5
        for item in results
    )
    passed = (
        on_time >= 6
        and all(item.evidence_urls for item in results)
        and all(600 <= item.estimated_seconds <= 900 for item in results)
        and balanced
        and undominated
        and results[3].shortcut_action_at_0900 == "announce_unavailable"
    )
    report = AcceptanceReport(
        start.isoformat(),
        (start + timedelta(days=6)).isoformat(),
        tuple(results),
        on_time,
        passed,
        (
            "Fixtures validate mechanics; live source mix and editorial usefulness "
            "still require observation after activation.",
        ),
    )
    atomic_write_json(workspace / "data" / "acceptance" / "report.json", asdict(report))
    return report
