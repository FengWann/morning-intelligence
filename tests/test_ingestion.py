"""Deterministic source-ingestion tests."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from news_intelligence.cli import main
from news_intelligence.ingestion import (
    CollectionResult,
    Source,
    collect,
    load_sources,
    parse_feed,
    parse_gdelt,
    result_json,
)

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 9, 12, 2, tzinfo=UTC)


def test_load_starter_sources_covers_four_lanes() -> None:
    sources = load_sources(Path("config/sources.example.json"))
    assert {source.lane for source in sources} >= {
        "politics",
        "business",
        "ai_technology",
        "singapore_asia",
    }
    assert {source.kind for source in sources} == {"rss", "gdelt"}


@pytest.mark.parametrize("value", [{}, {"sources": [1]}, {"sources": [{"id": "x"}]}])
def test_source_config_rejects_invalid_values(tmp_path: Path, value: object) -> None:
    path = tmp_path / "sources.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError):
        load_sources(path)


def test_source_config_rejects_duplicates_and_invalid_fields(tmp_path: Path) -> None:
    base = {
        "id": "x",
        "name": "X",
        "kind": "rss",
        "url": "https://x.test",
        "lane": "politics",
    }
    for sources in (
        [base, base],
        [{**base, "kind": "bad"}],
        [{**base, "language": 1}],
        [{**base, "kind": "gdelt"}],
    ):
        path = tmp_path / "sources.json"
        path.write_text(json.dumps({"sources": sources}), encoding="utf-8")
        with pytest.raises(ValueError):
            load_sources(path)


def test_rss_and_atom_parsing_filters_to_previous_24_hours() -> None:
    source = Source("feed", "Feed", "rss", "https://feed.test", "politics", "en")
    rss = parse_feed(
        (FIXTURES / "healthy.xml").read_bytes(),
        source,
        NOW.replace(day=11, hour=2),
        NOW,
    )
    atom = parse_feed(
        (FIXTURES / "atom.xml").read_bytes(), source, NOW.replace(day=11, hour=2), NOW
    )
    assert [item.title for item in rss] == ["Recent world event"]
    assert atom[0].url == "https://example.test/atom"
    assert atom[0].feed_summary == "Atom summary"


def test_gdelt_parsing_filters_and_preserves_metadata() -> None:
    source = Source(
        "gdelt", "GDELT", "gdelt", "https://api.test", "global", query="news"
    )
    articles = parse_gdelt(
        (FIXTURES / "gdelt.json").read_bytes(), source, NOW.replace(day=11, hour=2), NOW
    )
    assert len(articles) == 1
    assert articles[0].language == "English"
    assert articles[0].source_id == "gdelt"


def test_collection_isolates_broken_feed_and_returns_counts() -> None:
    sources = [
        Source("healthy", "Healthy", "rss", "fixture:healthy", "politics", "en"),
        Source("broken", "Broken", "rss", "fixture:broken", "business", "en"),
    ]

    def fetch(url: str) -> bytes:
        if url == "fixture:broken":
            raise OSError("fixture unavailable")
        return (FIXTURES / "healthy.xml").read_bytes()

    result = collect(sources, NOW, fetch)
    payload = json.loads(result_json(result))
    assert result.article_count == result.success_count == result.failure_count == 1
    assert payload["sources"][1] == {
        "source_id": "broken",
        "status": "failure",
        "article_count": 0,
        "error": "fixture unavailable",
    }


def test_collection_builds_gdelt_query_and_validates_time() -> None:
    source = Source(
        "gdelt", "GDELT", "gdelt", "https://api.test", "global", query="AI news"
    )
    requested = ""

    def fetch(url: str) -> bytes:
        nonlocal requested
        requested = url
        return (FIXTURES / "gdelt.json").read_bytes()

    assert collect([source], NOW, fetch).article_count == 1
    assert "query=AI+news" in requested and "startdatetime=" in requested
    with pytest.raises(ValueError, match="timezone-aware"):
        collect([], datetime(2026, 9, 12))


def test_malformed_source_payloads_become_failures() -> None:
    source = Source("feed", "Feed", "rss", "fixture:bad", "politics")
    result = collect([source], NOW, lambda _url: b"not xml")
    assert result.failure_count == 1


def test_live_collection_command_is_explicit_and_structured(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    config = tmp_path / "sources.json"
    config.write_text('{"sources": []}', encoding="utf-8")
    with pytest.raises(SystemExit, match="2"):
        main(["collect", "--sources", str(config)])

    empty = CollectionResult([], [], 0, 0, 0)
    monkeypatch.setattr("news_intelligence.cli.collect", lambda _sources, _now: empty)
    assert main(["collect", "--sources", str(config), "--live"]) == 0
    assert json.loads(capsys.readouterr().out)["article_count"] == 0
