"""Deterministic Article normalization and deduplication tests."""

from datetime import UTC, datetime

import pytest

from news_intelligence.ingestion import CollectedArticle
from news_intelligence.normalization import (
    articles_json,
    canonicalize_url,
    normalize_and_deduplicate,
    normalize_source_id,
    normalize_text,
)

NOW = datetime(2026, 9, 12, 2, tzinfo=UTC).isoformat()


def entry(
    title: str = "ＡＩ   regulation\nannounced",
    url: str = "https://EXAMPLE.test:443/news?utm_source=x&id=2&fbclid=y",
    published_at: str = "2026-09-12T09:00:00+08:00",
    summary: str | None = "A regulator announced new requirements for AI systems.",
) -> CollectedArticle:
    return CollectedArticle(
        "  BBC News! ", " BBC   News ", title, url, published_at, summary, "en", NOW
    )


def test_normalizes_article_schema_and_stable_identity() -> None:
    first = normalize_and_deduplicate([entry()])
    second = normalize_and_deduplicate([entry()])
    assert articles_json(first) == articles_json(second)
    article = first[0]
    assert article.title == "AI regulation announced"
    assert article.source_id == "bbc-news"
    assert article.source_name == "BBC News"
    assert article.canonical_url == "https://example.test/news?id=2"
    assert article.published_at == "2026-09-12T01:00:00+00:00"
    assert len(article.id) == len(article.content_hash) == 64
    assert article.status == "accepted"


@pytest.mark.parametrize(
    ("item", "reason"),
    [
        (entry(title=" \n "), "missing usable title"),
        (entry(url="ftp://example.test/news"), "missing usable URL"),
        (entry(published_at="yesterday"), "missing usable publication time"),
        (entry(published_at="2026-09-12T01:00:00"), "publication time"),
    ],
)
def test_rejects_invalid_required_fields(item: CollectedArticle, reason: str) -> None:
    article = normalize_and_deduplicate([item])[0]
    assert article.status == "rejected"
    assert reason in (article.rejection_reason or "")


def test_classifies_url_and_title_duplicates() -> None:
    original = entry()
    same_url = entry(title="Different title", url=original.url + "&utm_medium=email")
    same_title = entry(
        title="AI regulation announced",
        url="https://other.test/report",
        published_at="2026-09-10T02:00:00+00:00",
        summary="Different report.",
    )
    outside_window = entry(
        title="AI regulation announced",
        url="https://third.test/report",
        published_at="2026-09-10T00:59:59+00:00",
        summary="Unrelated content.",
    )
    results = normalize_and_deduplicate(
        [original, same_url, same_title, outside_window]
    )
    assert [item.status for item in results] == [
        "accepted",
        "duplicate",
        "duplicate",
        "accepted",
    ]
    assert "canonical URL" in (results[1].rejection_reason or "")
    assert "normalized title" in (results[2].rejection_reason or "")


def test_detects_exact_and_near_exact_syndicated_copies() -> None:
    text = "A long enough report says the company launched a new product worldwide."
    original = entry(title="Original", url="https://original.test/1", summary=text)
    exact = entry(title="Wire copy", url="https://wire.test/1", summary=text)
    near = entry(
        title="Syndicated copy",
        url="https://publisher.test/2",
        summary=text.replace("worldwide", "worldwid"),
    )
    different = entry(
        title="Another event",
        url="https://publisher.test/3",
        summary="This report concerns a separate election result in another country.",
    )
    results = normalize_and_deduplicate([original, exact, near, different])
    assert [item.status for item in results] == [
        "accepted",
        "duplicate",
        "duplicate",
        "accepted",
    ]
    assert "syndicated content" in (results[1].rejection_reason or "")
    assert "syndicated content" in (results[2].rejection_reason or "")


def test_helpers_cover_url_and_empty_content_edges() -> None:
    assert normalize_text(" x\t y ") == "x y"
    assert normalize_source_id("!!!") == ""
    assert canonicalize_url("not a URL") == ""
    assert canonicalize_url("https://example.test:invalid/news") == ""
    assert (
        canonicalize_url("http://Example.test:80?a=&gclid=x&b=2#fragment")
        == "http://example.test/?a=&b=2"
    )
    article = normalize_and_deduplicate([entry(summary=None)])[0]
    assert article.feed_summary is None
    assert article.content_hash == ""


def test_short_similar_summaries_are_not_treated_as_content_copies() -> None:
    first = entry(title="One", url="https://one.test", summary="Company update")
    second = entry(title="Two", url="https://two.test", summary="Company updates")
    assert normalize_and_deduplicate([first, second])[1].status == "accepted"
