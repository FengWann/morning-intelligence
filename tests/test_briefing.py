"""Fixture-based editorial checks for brief generation."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from news_intelligence.briefing import (
    BriefDraft,
    Claim,
    build_input,
    deterministic_draft,
    estimate_speech_seconds,
    generate_brief,
    render_brief,
)
from news_intelligence.clustering import Event, Importance
from news_intelligence.ingestion import CollectedArticle
from news_intelligence.normalization import Article, normalize_and_deduplicate
from news_intelligence.ranking import RankedEvent


def article(source: str, number: int, summary: str) -> Article:
    raw = CollectedArticle(
        source,
        source.upper(),
        f"Leader claims policy outcome {number}",
        f"https://{source}.test/{number}",
        "2026-09-12T01:00:00+00:00",
        summary,
        "en",
        "2026-09-12T02:00:00+00:00",
    )
    return normalize_and_deduplicate([raw])[0]


def ranked(
    identity: str, evidence: list[Article], category: str = "Politics"
) -> RankedEvent:
    event = Event(
        identity,
        "Policy dispute",
        evidence[0].feed_summary or evidence[0].title,
        "2026-09-12T01:00:00+00:00",
        "2026-09-12T02:00:00+00:00",
        [item.id for item in evidence],
        len({item.source_id for item in evidence}),
        ["SG"],
        ["policy"],
        ["Leader"],
        Importance(total=80, rationale="two source reports"),
        "high",
    )
    return RankedEvent(event, category, (), 120)  # type: ignore[arg-type]


def test_fixture_dispute_history_warning_sources_and_speech(tmp_path: Path) -> None:
    reuters = article("reuters", 1, "Government claims the policy reduced costs")
    bbc = article("bbc", 2, "Opposition denies the reported cost reduction")
    data = build_input(
        "2026-09-12",
        [ranked("event-1", [reuters, bbc])],
        {reuters.id: reuters, bbc.id: bbc},
        tmp_path,
    )
    result = generate_brief(data, minimum_seconds=1, maximum_seconds=900)
    assert data.insufficient_history
    assert data.events[0].disputed
    assert "REUTERS称" in result.markdown
    assert "BBC称" in result.markdown
    assert "历史数据不足" in result.markdown
    assert "[REUTERS](https://reuters.test/1)" in result.markdown
    assert "http" not in result.speech_text
    assert "各方主张" in result.speech_text
    assert result.estimated_seconds == estimate_speech_seconds(result.speech_text)


def test_seven_archives_compare_identity_without_calling_repetition_a_trend(
    tmp_path: Path,
) -> None:
    for day in range(1, 9):
        (tmp_path / f"2026-09-{day:02}.json").write_text(
            json.dumps([{"id": "old"}]), encoding="utf-8"
        )
    source = article("reuters", 1, "Company announces a new market policy")
    data = build_input(
        "2026-09-12",
        [ranked("new", [source], "Business")],
        {source.id: source},
        tmp_path,
    )
    draft = deterministic_draft(data)
    assert not data.insufficient_history
    assert len(data.prior_events) == 7
    assert "不等同于趋势" in draft.what_changed[0].text


def test_invalid_evidence_unknown_claim_and_disputed_fact_are_rejected(
    tmp_path: Path,
) -> None:
    bad = replace(article("reuters", 1, "Government claims success"), canonical_url="")
    with pytest.raises(ValueError, match="no valid evidence URL"):
        build_input("2026-09-12", [ranked("bad", [bad])], {bad.id: bad}, tmp_path)

    source = article("reuters", 2, "Government claims success")
    data = build_input(
        "2026-09-12", [ranked("event", [source])], {source.id: source}, tmp_path
    )
    base = deterministic_draft(data)
    unknown = replace(
        base,
        things_to_watch=(Claim("x", "analysis", "missing", (source.id,)),),
    )
    with pytest.raises(ValueError, match="unknown event"):
        render_brief(data, unknown, minimum_seconds=0)
    unsupported = replace(
        base,
        things_to_watch=(Claim("x", "analysis", "event", ("missing",)),),
    )
    with pytest.raises(ValueError, match="exceeds supplied evidence"):
        render_brief(data, unsupported, minimum_seconds=0)
    asserted = replace(
        base,
        sections={"Politics": (Claim("certain", "fact", "event", (source.id,)),)},
    )
    with pytest.raises(ValueError, match="cannot be stated as fact"):
        render_brief(data, asserted, minimum_seconds=0)


def test_independent_dispute_requires_attribution_and_duration_is_enforced(
    tmp_path: Path,
) -> None:
    first = article("reuters", 1, "Government claims success")
    second = article("bbc", 2, "Opposition denies success")
    data = build_input(
        "2026-09-12",
        [ranked("event", [first, second])],
        {first.id: first, second.id: second},
        tmp_path,
    )
    draft = deterministic_draft(data)
    no_accounts = replace(draft, sections={"Politics": ()})
    with pytest.raises(ValueError, match="must remain attributed"):
        render_brief(data, no_accounts, minimum_seconds=0)
    with pytest.raises(ValueError, match="outside 600-900s"):
        render_brief(data, draft)


def test_single_source_warning_and_injected_generator(tmp_path: Path) -> None:
    source = article("reuters", 1, "Government claims success")
    data = build_input(
        "2026-09-12", [ranked("event", [source])], {source.id: source}, tmp_path
    )
    called = False

    def generator(value: object) -> BriefDraft:
        nonlocal called
        called = value is data
        return deterministic_draft(data)

    result = generate_brief(
        data, generator=generator, minimum_seconds=0, maximum_seconds=900
    )
    assert called
    assert result.warnings == (
        "单一来源警告：Policy dispute",
        "历史数据不足：What Changed? 暂不判断趋势。",
    )


def test_valid_ten_minute_draft_and_url_in_speech_are_checked(tmp_path: Path) -> None:
    source = article("reuters", 1, "Company announces a policy")
    data = build_input(
        "2026-09-12",
        [ranked("event", [source], "Business")],
        {source.id: source},
        tmp_path,
    )
    data = replace(data, insufficient_history=False)
    draft = BriefDraft("中" * 1800, {}, (), ())
    result = render_brief(data, draft)
    assert 600 <= result.estimated_seconds <= 900
    assert not result.warnings
    with pytest.raises(ValueError, match="contains URL"):
        render_brief(data, replace(draft, opening="https://example.test" * 100))
