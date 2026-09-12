"""Tests for conservative event clustering."""

import json
from dataclasses import replace
from pathlib import Path

from news_intelligence.clustering import archive_events, cluster_articles
from news_intelligence.ingestion import CollectedArticle
from news_intelligence.normalization import Article, normalize_and_deduplicate


def make(title: str, source: str, hour: int, summary: str) -> Article:
    raw = CollectedArticle(
        source,
        source.upper(),
        title,
        f"https://{source}.test/{hour}-{len(title)}",
        f"2026-09-12T{hour:02}:00:00+00:00",
        summary,
        "en",
        "2026-09-12T12:00:00+00:00",
    )
    return normalize_and_deduplicate([raw])[0]


def test_same_occurrence_merges_but_same_topic_different_action_splits() -> None:
    launch = make(
        "OpenAI launches Atlas model in Singapore",
        "reuters",
        1,
        "OpenAI launches its Atlas model in Singapore today",
    )
    coverage = make(
        "OpenAI launches Atlas model in Singapore today",
        "bbc",
        2,
        "The OpenAI Atlas model launches in Singapore today",
    )
    lawsuit = make(
        "OpenAI sued over Atlas model in Singapore",
        "ap",
        3,
        "OpenAI sued over its Atlas model in Singapore",
    )
    events = cluster_articles([launch, coverage, lawsuit])
    assert [len(event.article_ids) for event in events] == [2, 1]
    assert events[0].distinct_source_count == 2
    assert events[0].confidence == "high"


def test_ambiguous_pairs_require_reasoner_and_reasoner_is_only_ambiguous() -> None:
    first = make(
        "Nvidia announces Blackwell supply agreement",
        "reuters",
        1,
        "Nvidia signs a Blackwell supply agreement with Acme",
    )
    ambiguous = make(
        "Nvidia Blackwell agreement reaches Acme",
        "bbc",
        2,
        "Acme confirms the Nvidia Blackwell supply deal",
    )
    calls = 0

    def approve(_article: Article, _event: object) -> bool:
        nonlocal calls
        calls += 1
        return True

    assert len(cluster_articles([first, ambiguous])) == 2
    merged = cluster_articles([first, ambiguous], reasoner=approve)
    assert len(merged) == 1 and calls == 1


def test_stable_id_update_syndication_and_archive(tmp_path: Path) -> None:
    first = make(
        "Microsoft launches Copilot feature in Japan",
        "reuters",
        1,
        "Microsoft launches a Copilot feature in Japan today",
    )
    syndicated = replace(
        make(
            "Microsoft launches Copilot feature in Japan today",
            "reuters",
            2,
            "Microsoft launches the Copilot feature in Japan today",
        ),
        source_name="Reuters Partner",
    )
    initial = cluster_articles([first])
    rerun = cluster_articles([first, syndicated], prior_events=initial)
    assert rerun[0].id == initial[0].id
    assert rerun[0].distinct_source_count == 1
    path = archive_events(tmp_path, "2026-09-12", rerun)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload[0]["id"] == initial[0].id
    assert payload[0]["importance"]["total"] == 0


def test_filters_duplicates_and_separates_outside_window_and_metadata_conflicts() -> (
    None
):
    first = replace(
        make(
            "Acme announces factory expansion",
            "bbc",
            1,
            "Acme announces factory expansion in London",
        ),
        country="GB",
        topics=["business"],
    )
    late = replace(
        make(
            "Acme announces factory expansion",
            "ap",
            2,
            "Acme announces factory expansion in London",
        ),
        published_at="2026-09-15T02:00:00+00:00",
    )
    conflict = replace(
        make(
            "Acme announces factory expansion",
            "cna",
            3,
            "Acme announces factory expansion in London",
        ),
        country="SG",
        topics=["technology"],
    )
    duplicate = replace(make("unused", "x", 4, "unused"), status="duplicate")
    assert len(cluster_articles([first, late, conflict, duplicate])) == 3
