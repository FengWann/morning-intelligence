"""Tests for deterministic event ranking and balanced selection."""

from dataclasses import replace

from news_intelligence.clustering import Event, Importance
from news_intelligence.ingestion import CollectedArticle
from news_intelligence.normalization import Article, normalize_and_deduplicate
from news_intelligence.ranking import rank_events, score_event, select_events


def article(source: str, number: int) -> Article:
    return normalize_and_deduplicate(
        [
            CollectedArticle(
                source,
                source.upper(),
                f"Evidence {number}",
                f"https://{source}.test/{number}",
                "2026-09-12T01:00:00+00:00",
                f"Evidence summary {number}",
                "en",
                "2026-09-12T02:00:00+00:00",
            )
        ]
    )[0]


def event(
    identity: str,
    title: str,
    evidence: list[Article],
    *,
    countries: list[str] | None = None,
) -> Event:
    return Event(
        identity,
        title,
        title,
        "2026-09-12T01:00:00+00:00",
        "2026-09-12T02:00:00+00:00",
        [item.id for item in evidence],
        len({item.source_id for item in evidence}),
        countries or [],
        [],
        [title.split()[0]],
        Importance(),
        "low",
    )


def test_score_has_all_dimensions_rationales_and_confidence_labels() -> None:
    single = article("blog", 1)
    ranked = score_event(
        event("one", "Company market news", [single]), {single.id: single}
    )
    assert ranked.category == "Business"
    assert ranked.labels == ("single-source", "low-confidence")
    assert ranked.event.confidence == "low"
    assert 0 <= ranked.event.importance.total <= 100
    for name in (
        "impact",
        "breadth",
        "novelty",
        "momentum",
        "source_quality",
        "user_relevance",
        "total",
    ):
        assert f"{name}=" in ranked.event.importance.rationale


def test_authoritative_corroboration_improves_score_and_confidence() -> None:
    blog = article("blog", 1)
    reuters = article("reuters", 2)
    bbc = article("bbc", 3)
    weak = event("weak", "AI model launch", [blog])
    strong = event("strong", "AI model launch", [reuters, bbc], countries=["US"])
    lookup = {item.id: item for item in (blog, reuters, bbc)}
    weak_ranked = score_event(weak, lookup)
    strong_ranked = score_event(strong, lookup)
    assert strong_ranked.event.importance.total > weak_ranked.event.importance.total
    assert strong_ranked.event.confidence == "high"
    assert strong_ranked.labels == ()


def test_deterministic_balanced_order_duplicate_prevention_and_budget() -> None:
    sources = [
        article(name, number)
        for number, name in enumerate(("reuters", "bbc", "cna"), 1)
    ]
    lookup = {item.id: item for item in sources}
    fixtures = [
        event("p1", "Government election policy", sources),
        event("p2", "Minister election policy", sources),
        event("b1", "Company market trade", sources),
        event("a1", "AI software model", sources),
        event("s1", "Singapore policy", sources, countries=["SG"]),
    ]
    first = rank_events(fixtures, lookup)
    second = rank_events(list(reversed(fixtures)), lookup)
    assert [item.event.id for item in first] == [item.event.id for item in second]
    selected = select_events(first + first, max_spoken_seconds=480)
    assert [item.category for item in selected] == [
        "Politics",
        "Business",
        "AI/Technology",
        "Singapore/Asia",
    ]
    assert len({item.event.id for item in selected}) == len(selected)
    assert sum(item.estimated_seconds for item in selected) <= 480


def test_weak_items_are_not_quota_filler_and_small_budget_stops() -> None:
    source = article("blog", 1)
    item = score_event(
        event("weak", "Miscellaneous item", [source]), {source.id: source}
    )
    item = replace(
        item,
        event=replace(item.event, importance=replace(item.event.importance, total=10)),
    )
    assert select_events([item], minimum_score=45) == []
    assert select_events([item], minimum_score=0, max_spoken_seconds=100) == []


def test_duplicate_only_queue_is_exhausted_without_reselection() -> None:
    source = article("reuters", 1)
    item = score_event(
        event("same", "Government election", [source]), {source.id: source}
    )
    selected = select_events([item, item], minimum_score=0, max_spoken_seconds=240)
    assert selected == [item]
