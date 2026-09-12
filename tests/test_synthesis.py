from dataclasses import replace

import pytest

from news_intelligence.clustering import Event, Importance
from news_intelligence.synthesis import (
    HistoricalTheme,
    ImpactLink,
    IntelligenceTheme,
    OpportunityHypothesis,
    ProblemSignal,
    SynthesisEvent,
    ThemeEvidence,
    build_fallback_theme,
    choose_opportunity,
    classify_change,
    group_related_events,
    parse_proposed_theme,
    score_theme,
    select_themes,
    stable_theme_id,
    validate_opportunity,
    validate_theme,
)


def event(event_id: str) -> Event:
    return Event(
        event_id,
        "Port delays rise",
        "Port delays rise",
        "2026-09-12T00:00:00+00:00",
        "2026-09-12T01:00:00+00:00",
        [event_id + "-article"],
        1,
        ["SG"],
        ["business"],
        ["PortCo"],
        Importance(),
        "low",
    )


def synthesis_event(
    event_id: str,
    *,
    mechanism: str = "shipping-delay",
    entity: str = "PortCo",
    actor: str = "importers",
    geography: str = "Singapore",
    chain: str = "chain-a",
    development: str = "development-a",
    direction: str = "worsening",
) -> SynthesisEvent:
    return SynthesisEvent(
        event(event_id),
        (ThemeEvidence(event_id, "Reuters", f"https://example.com/{event_id}"),),
        (entity,),
        (actor,),
        (geography,),
        mechanism,
        ("Business", "Singapore/Asia"),
        ("logistics",),
        (chain,),
        development,
        direction,
        "portco-importers-singapore-shipping-delay",
    )


def theme(
    *, event_ids: tuple[str, ...] = ("e1",), score: int = 60
) -> IntelligenceTheme:
    identity = stable_theme_id(
        ("PortCo",), ("importers",), ("Singapore",), "shipping-delay"
    )
    evidence = tuple(
        ThemeEvidence(item, "Reuters", f"https://x.test/{item}") for item in event_ids
    )
    impact = ImpactLink(
        "港口延误增加",
        "库存补充变慢",
        ("进口商",),
        "库存成本可能上升",
        "medium",
        event_ids,
    )
    problem = ProblemSignal("到货时间难以预测", ("进口商",), "operational", event_ids)
    return IntelligenceTheme(
        identity,
        "2026-09-12",
        "港口延误正在增加供应链压力",
        "多项事件共同显示进口商的交付风险正在上升。",
        ("Business", "Singapore/Asia"),
        event_ids,
        evidence,
        "continuing",
        "本日出现新的港口延误事件。",
        (impact,),
        (problem,),
        ("部分港口仍正常运行。",),
        ("延误持续时间尚不明确。",),
        "medium",
        score,
        "证据来自多个事件，仍存在不确定性。",
    )


def opportunity() -> OpportunityHypothesis:
    return OpportunityHypothesis(
        "到货时间难以预测",
        ("进口商",),
        "目前依赖人工查看承运商状态。",
        "不同来源更新不一致，人工汇总较慢。",
        "AI只负责归一化状态并提示异常。",
        "可测试一个运输异常汇总工具。",
        ("供应链负责人",),
        ("e1",),
        ("用户确实需要更早收到预警。",),
        "访谈三名进口商并核对当前流程。",
        "low",
    )


def test_stable_id_is_order_and_wording_independent() -> None:
    left = stable_theme_id(("PortCo", "Carrier"), ("Importer",), ("SG",), "Delay")
    right = stable_theme_id(("carrier", "portco"), ("importer",), ("sg",), "delay")
    assert left == right
    with pytest.raises(ValueError):
        stable_theme_id((), (), (), "")


def test_grouping_requires_mechanism_and_semantic_anchor() -> None:
    base = synthesis_event("e1")
    related = synthesis_event("e2", chain="chain-b", development="development-b")
    keyword_only = replace(
        synthesis_event("e3", mechanism="inflation", entity="OtherCo"), theme_key=""
    )
    no_actor_or_place = replace(
        synthesis_event("e4", actor="retailers", geography="Malaysia"), theme_key=""
    )
    groups = group_related_events((keyword_only, related, no_actor_or_place, base))
    assert sorted(len(group) for group in groups) == [1, 1, 2]
    conflict = replace(related, theme_key="different-semantic-theme")
    assert [len(group) for group in group_related_events((base, conflict))] == [1, 1]


def test_group_identity_stays_stable_when_related_event_is_added() -> None:
    base = synthesis_event("e1")
    added = replace(
        synthesis_event("e2"),
        principal_entities=("PortCo", "CarrierCo"),
        affected_actors=("importers", "retailers"),
        geographies=("Singapore", "Malaysia"),
    )
    single = build_fallback_theme((base,), "2026-09-12")
    combined = build_fallback_theme((base, added), "2026-09-12")
    assert single.id == combined.id


def test_fallback_is_narrow_valid_and_labels_history() -> None:
    result = build_fallback_theme((synthesis_event("e1"),), "2026-09-12")
    assert result.change_state == "insufficient_history"
    assert result.confidence == "low"
    validate_theme(result, {"e1"})
    with pytest.raises(ValueError):
        build_fallback_theme((), "2026-09-12")


@pytest.mark.parametrize(
    ("history", "expected"),
    [
        ((), "insufficient_history"),
        (
            (HistoricalTheme("2026-09-11", "failed", "x", (), ()),),
            "insufficient_history",
        ),
        ((HistoricalTheme("2026-09-11", "complete", "different", (), ()),), "new"),
    ],
)
def test_history_missing_invalid_and_new(
    history: tuple[HistoricalTheme, ...], expected: str
) -> None:
    assert classify_change((synthesis_event("e1"),), history, "2026-09-12") == expected


def test_change_states_and_false_acceleration_prevention() -> None:
    current = synthesis_event("e1")
    identity = build_fallback_theme((current,), "2026-09-12").id
    prior = HistoricalTheme(
        "2026-09-10",
        "complete",
        identity,
        ("development-a",),
        ("chain-a",),
        ("Singapore",),
        ("logistics",),
        ("importers",),
        "worsening",
    )
    assert classify_change((current,), (prior,), "2026-09-12") == "unchanged"
    repeated = replace(current, event=event("e2"), development_id="development-a")
    assert classify_change((current, repeated), (prior,), "2026-09-12") == "unchanged"
    changed = replace(current, development_id="development-b")
    assert classify_change((changed,), (prior,), "2026-09-12") == "continuing"
    turned = replace(changed, direction="improving")
    assert classify_change((turned,), (prior,), "2026-09-12") == "turning"

    recent = replace(
        prior,
        reporting_date="2026-09-08",
        evidentiary_chain_ids=("a", "b", "c"),
    )
    middle = replace(
        prior, reporting_date="2026-08-20", evidentiary_chain_ids=("a", "b")
    )
    long = replace(prior, reporting_date="2026-06-20", evidentiary_chain_ids=("a",))
    fillers = tuple(
        replace(prior, reporting_date=f"2026-09-{day:02d}") for day in range(1, 8)
    ) + tuple(
        replace(prior, reporting_date=f"2026-08-{day:02d}") for day in range(1, 24)
    )
    expanded = replace(changed, evidentiary_chain_ids=("a", "b", "c", "d"))
    history = (recent, middle, long, *fillers)
    assert classify_change((expanded,), history, "2026-09-12") == "accelerating"

    syndicated = replace(
        expanded, event=event("e2"), evidentiary_chain_ids=("a", "a", "a")
    )
    assert classify_change((syndicated,), history, "2026-09-12") == "continuing"


def test_validation_rejects_unknown_bad_urls_and_ungrounded_claims() -> None:
    valid = theme()
    validate_theme(valid, {"e1"})
    with pytest.raises(ValueError):
        validate_theme(replace(valid, reporting_date="bad"), {"e1"})
    with pytest.raises(ValueError):
        validate_theme(replace(valid, id="bad"), {"e1"})
    with pytest.raises(ValueError):
        validate_theme(replace(valid, title_zh="English"), {"e1"})
    with pytest.raises(ValueError):
        validate_theme(replace(valid, score=101), {"e1"})
    with pytest.raises(ValueError):
        validate_theme(replace(valid, event_ids=("unknown",)), {"e1"})
    with pytest.raises(ValueError):
        validate_theme(replace(valid, evidence=()), {"e1"})
    bad_evidence = (ThemeEvidence("e1", "x", "file:///private"),)
    with pytest.raises(ValueError):
        validate_theme(replace(valid, evidence=bad_evidence), {"e1"})
    bad_impact = replace(valid.impact_chain[0], evidence_event_ids=())
    with pytest.raises(ValueError):
        validate_theme(replace(valid, impact_chain=(bad_impact,)), {"e1"})
    bad_problem = replace(valid.problem_signals[0], who_has_it_zh=())
    with pytest.raises(ValueError):
        validate_theme(replace(valid, problem_signals=(bad_problem,)), {"e1"})


def test_structured_parser_and_validation() -> None:
    original = theme()
    payload = {
        "id": original.id,
        "reporting_date": original.reporting_date,
        "title_zh": original.title_zh,
        "thesis_zh": original.thesis_zh,
        "lanes": list(original.lanes),
        "event_ids": list(original.event_ids),
        "evidence": [
            {"event_id": "e1", "source_name": "Reuters", "url": "https://x.test/e1"}
        ],
        "change_state": original.change_state,
        "change_summary_zh": original.change_summary_zh,
        "impact_chain": [
            {
                "cause_zh": "港口延误增加",
                "mechanism_zh": "库存补充变慢",
                "affected_actors_zh": ["进口商"],
                "effect_zh": "库存成本可能上升",
                "confidence": "medium",
                "evidence_event_ids": ["e1"],
            }
        ],
        "problem_signals": [
            {
                "problem_zh": "到货时间难以预测",
                "who_has_it_zh": ["进口商"],
                "type": "operational",
                "evidence_event_ids": ["e1"],
            }
        ],
        "counter_evidence_zh": ["部分港口仍正常运行。"],
        "uncertainties_zh": ["持续时间未知。"],
        "confidence": "medium",
        "score": 60,
        "score_rationale_zh": "证据足够但仍有不确定性。",
    }
    parsed = parse_proposed_theme(payload)
    validate_theme(parsed, {"e1"})
    assert parsed == original or parsed.title_zh == original.title_zh
    with pytest.raises(ValueError):
        parse_proposed_theme({**payload, "lanes": "Business"})
    with pytest.raises(ValueError):
        parse_proposed_theme({**payload, "evidence": "bad"})


def test_opportunity_gate_and_single_selection() -> None:
    valid_theme = theme()
    proposal = opportunity()
    validate_opportunity(proposal, valid_theme)
    ungrounded = replace(proposal, problem_zh="不存在的问题")
    with pytest.raises(ValueError):
        validate_opportunity(ungrounded, valid_theme)
    prohibited = replace(proposal, gap_zh="客户已经验证愿意付费。")
    with pytest.raises(ValueError):
        validate_opportunity(prohibited, valid_theme)
    assert choose_opportunity(((ungrounded, valid_theme),)) is None
    stronger = replace(valid_theme, id="theme_1111111111111111", score=90)
    assert (
        choose_opportunity(((proposal, valid_theme), (proposal, stronger))) == proposal
    )


def test_scoring_penalties_and_selection_without_filler() -> None:
    base = theme()
    scored = score_theme(
        base,
        material_change=80,
        expected_impact=70,
        user_relevance=90,
        breadth=60,
        novelty=50,
    )
    assert 0 <= scored.score <= 100
    assert "扣分" in scored.score_rationale_zh
    with pytest.raises(ValueError):
        score_theme(
            base,
            material_change=101,
            expected_impact=0,
            user_relevance=0,
            breadth=0,
            novelty=0,
        )

    themes = [
        replace(scored, id=f"theme_{index:016d}", score=value, lanes=(lane,))
        for index, (value, lane) in enumerate(
            (
                (90, "Business"),
                (80, "Politics"),
                (70, "AI/Technology"),
                (65, "Singapore/Asia"),
                (20, "Business"),
            )
        )
    ]
    assert len(select_themes(themes)) == 4
    unchanged = replace(themes[0], change_state="unchanged")
    assert unchanged not in select_themes((unchanged, *themes[1:]))
