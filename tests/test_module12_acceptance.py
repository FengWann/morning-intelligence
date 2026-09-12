"""Deterministic end-to-end acceptance for Module 12 delivery contracts."""

import json
from dataclasses import asdict, replace

from news_intelligence.clustering import Event, Importance
from news_intelligence.publishing import (
    Publication,
    PublicEvent,
    PublicSource,
    render_intelligence_markdown,
)
from news_intelligence.synthesis import (
    HistoricalTheme,
    ImpactLink,
    IntelligenceTheme,
    ProblemSignal,
    SynthesisEvent,
    ThemeEvidence,
    classify_change,
    stable_theme_id,
)
from news_intelligence.wechat import messages_from_publication


def _event(event_id: str) -> Event:
    return Event(
        event_id,
        "Port delays rise",
        "Port delays rise",
        "2026-09-12T00:00:00+00:00",
        "2026-09-12T01:00:00+00:00",
        [f"{event_id}-article"],
        1,
        ["SG"],
        ["business"],
        ["PortCo"],
        Importance(),
        "medium",
    )


def _synthesis_event(event_id: str) -> SynthesisEvent:
    return SynthesisEvent(
        _event(event_id),
        (ThemeEvidence(event_id, "Reuters", f"https://example.test/{event_id}"),),
        ("PortCo",),
        ("importers",),
        ("Singapore",),
        "shipping-delay",
        ("Business", "Singapore/Asia"),
        ("logistics",),
        ("independent-chain-a",),
        "same-development",
        "worsening",
    )


def _theme(event_id: str, *, score: int, suffix: str) -> IntelligenceTheme:
    identity = stable_theme_id(
        (f"PortCo-{suffix}",), ("importers",), ("Singapore",), "shipping-delay"
    )
    return IntelligenceTheme(
        identity,
        "2026-09-12",
        f"港口变化正在增加供应链压力（{suffix}）",
        "新变化正在推高进口商的交付风险。",
        ("Business", "Singapore/Asia"),
        (event_id,),
        (ThemeEvidence(event_id, "Reuters", f"https://example.test/{event_id}"),),
        "continuing",
        "出现了新的可核实进展，而不是报道数量增加。",
        (
            ImpactLink(
                "港口延误增加",
                "库存补充变慢",
                ("进口商",),
                "库存成本可能上升",
                "medium",
                (event_id,),
            ),
        ),
        (ProblemSignal("到货时间难以预测", ("进口商",), "operational", (event_id,)),),
        ("部分港口仍正常运行。",),
        ("延误持续时间未知。",),
        "medium",
        score,
        "证据支持变化，但仍有反证。",
    )


def test_deterministic_seven_day_synthesis_and_delivery_acceptance() -> None:
    repeated = _synthesis_event("event-1")
    identity = stable_theme_id(
        repeated.principal_entities,
        repeated.affected_actors,
        repeated.geographies,
        repeated.mechanism,
    )
    history = tuple(
        HistoricalTheme(
            f"2026-09-{day:02d}",
            "complete",
            identity,
            ("same-development",),
            ("independent-chain-a",),
            ("Singapore",),
            ("logistics",),
            ("importers",),
            "worsening",
        )
        for day in range(5, 12)
    )

    # Seven days of syndicated volume do not create a material change or acceleration.
    syndicated_copy = replace(repeated, event=_event("event-2"))
    assert classify_change((repeated, syndicated_copy), history, "2026-09-12") == (
        "unchanged"
    )

    strong = tuple(
        _theme(f"event-{index}", score=score, suffix=str(index))
        for index, score in enumerate((90, 80, 70, 65), start=1)
    )
    weak = _theme("event-5", score=20, suffix="weak")
    events = tuple(
        PublicEvent(
            f"event-{index}",
            "Source headline",
            "Source summary",
            "medium",
            (PublicSource("Reuters", f"https://example.test/event-{index}"),),
        )
        for index in range(1, 6)
    )
    publication = Publication(
        "2026-09-12",
        "complete",
        "https://example.test/briefs/2026-09-12.md",
        "旧语音稿不得驱动结构化消息。",
        "2026-09-12T08:40:00+08:00",
        events,
        (*strong, weak),
    )

    markdown = render_intelligence_markdown(publication)
    assert "**核心判断：** 新变化正在推高进口商的交付风险。" in markdown
    assert "[Reuters](https://example.test/event-1)（事件 event-1）" in markdown

    payload = json.loads(json.dumps(asdict(publication), ensure_ascii=False))
    messages = messages_from_publication(payload)
    assert len(messages) == 5
    assert all(message.body.startswith("核心判断：") for message in messages[:4])
    assert all("https://example.test/" in message.body for message in messages[:4])
    assert not any("weak" in message.title for message in messages)
    assert messages[-1].title.endswith("变化与机会雷达")
