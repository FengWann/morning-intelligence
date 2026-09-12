"""Evidence-first, deterministic synthesis of events into intelligence themes."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from typing import Literal, cast
from urllib.parse import urlparse

from news_intelligence.clustering import Event

Confidence = Literal["high", "medium", "low"]
ChangeState = Literal[
    "new", "continuing", "accelerating", "turning", "unchanged", "insufficient_history"
]
ProblemType = Literal[
    "regulatory", "cost", "labor", "technology", "operational", "consumer", "market"
]
_CONFIDENCE = {"high", "medium", "low"}
_CHANGE_STATES = {
    "new",
    "continuing",
    "accelerating",
    "turning",
    "unchanged",
    "insufficient_history",
}
_PROBLEM_TYPES = {
    "regulatory",
    "cost",
    "labor",
    "technology",
    "operational",
    "consumer",
    "market",
}
_CJK = re.compile(r"[\u3400-\u9fff]")
_ID_PART = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class ThemeEvidence:
    event_id: str
    source_name: str
    url: str


@dataclass(frozen=True)
class ImpactLink:
    cause_zh: str
    mechanism_zh: str
    affected_actors_zh: tuple[str, ...]
    effect_zh: str
    confidence: Confidence
    evidence_event_ids: tuple[str, ...]


@dataclass(frozen=True)
class ProblemSignal:
    problem_zh: str
    who_has_it_zh: tuple[str, ...]
    type: ProblemType
    evidence_event_ids: tuple[str, ...]


@dataclass(frozen=True)
class OpportunityHypothesis:
    problem_zh: str
    who_has_it_zh: tuple[str, ...]
    current_solution_zh: str
    gap_zh: str
    ai_leverage_zh: str
    potential_product_zh: str
    potential_buyer_zh: tuple[str, ...]
    evidence_event_ids: tuple[str, ...]
    key_assumptions_zh: tuple[str, ...]
    next_validation_step_zh: str
    confidence: Confidence


@dataclass(frozen=True)
class IntelligenceTheme:
    id: str
    reporting_date: str
    title_zh: str
    thesis_zh: str
    lanes: tuple[str, ...]
    event_ids: tuple[str, ...]
    evidence: tuple[ThemeEvidence, ...]
    change_state: ChangeState
    change_summary_zh: str
    impact_chain: tuple[ImpactLink, ...]
    problem_signals: tuple[ProblemSignal, ...]
    counter_evidence_zh: tuple[str, ...]
    uncertainties_zh: tuple[str, ...]
    confidence: Confidence
    score: int
    score_rationale_zh: str


@dataclass(frozen=True)
class SynthesisEvent:
    """Explicit semantic metadata used to avoid keyword-only event joins."""

    event: Event
    evidence: tuple[ThemeEvidence, ...]
    principal_entities: tuple[str, ...]
    affected_actors: tuple[str, ...]
    geographies: tuple[str, ...]
    mechanism: str
    lanes: tuple[str, ...]
    industries: tuple[str, ...] = ()
    evidentiary_chain_ids: tuple[str, ...] = ()
    development_id: str = ""
    direction: str = ""
    theme_key: str = ""


@dataclass(frozen=True)
class HistoricalTheme:
    reporting_date: str
    status: str
    theme_id: str
    development_ids: tuple[str, ...]
    evidentiary_chain_ids: tuple[str, ...]
    geographies: tuple[str, ...] = ()
    industries: tuple[str, ...] = ()
    affected_actors: tuple[str, ...] = ()
    direction: str = ""


def _nonempty_zh(value: str, field: str) -> None:
    if not value.strip() or not _CJK.search(value):
        raise ValueError(f"{field} must contain Chinese text")


def stable_theme_id(
    principal_entities: Iterable[str],
    affected_actors: Iterable[str],
    geographies: Iterable[str],
    mechanism: str,
) -> str:
    """Create a wording-independent identity from explicit semantic dimensions."""
    dimensions = [
        sorted(
            {
                _ID_PART.sub("-", item.casefold()).strip("-")
                for item in values
                if item.strip()
            }
        )
        for values in (principal_entities, affected_actors, geographies)
    ]
    mechanism_key = _ID_PART.sub("-", mechanism.casefold()).strip("-")
    if not mechanism_key or not any(dimensions):
        raise ValueError("stable identity requires a mechanism and semantic actors")
    identity = "|".join(",".join(items) for items in dimensions) + "|" + mechanism_key
    return "theme_" + hashlib.sha256(identity.encode()).hexdigest()[:16]


def _valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_theme(theme: IntelligenceTheme, known_event_ids: Iterable[str]) -> None:
    """Reject invalid structure and every evidence reference outside supplied events."""
    known = set(known_event_ids)
    try:
        date.fromisoformat(theme.reporting_date)
    except ValueError as exc:
        raise ValueError("invalid reporting_date") from exc
    if not theme.id.startswith("theme_") or len(theme.id) != 22:
        raise ValueError("invalid stable theme id")
    _nonempty_zh(theme.title_zh, "title_zh")
    _nonempty_zh(theme.thesis_zh, "thesis_zh")
    _nonempty_zh(theme.change_summary_zh, "change_summary_zh")
    _nonempty_zh(theme.score_rationale_zh, "score_rationale_zh")
    if theme.change_state not in _CHANGE_STATES:
        raise ValueError("invalid change_state")
    if theme.confidence not in _CONFIDENCE:
        raise ValueError("invalid confidence")
    if not 0 <= theme.score <= 100:
        raise ValueError("score must be between 0 and 100")
    event_ids = set(theme.event_ids)
    if not event_ids or not event_ids <= known:
        raise ValueError("theme references unknown or no events")
    if not theme.evidence:
        raise ValueError("theme has no evidence")
    evidenced = {item.event_id for item in theme.evidence}
    if evidenced != event_ids or any(
        not _valid_url(item.url) for item in theme.evidence
    ):
        raise ValueError("theme evidence is invalid or incomplete")
    for link in theme.impact_chain:
        _nonempty_zh(link.cause_zh, "impact cause")
        _nonempty_zh(link.mechanism_zh, "impact mechanism")
        _nonempty_zh(link.effect_zh, "impact effect")
        if link.confidence not in _CONFIDENCE or not link.affected_actors_zh:
            raise ValueError("invalid impact link")
        _validate_refs(link.evidence_event_ids, event_ids)
    for signal in theme.problem_signals:
        _nonempty_zh(signal.problem_zh, "problem")
        if signal.type not in _PROBLEM_TYPES or not signal.who_has_it_zh:
            raise ValueError("invalid problem signal")
        _validate_refs(signal.evidence_event_ids, event_ids)


def _validate_refs(references: Sequence[str], allowed: set[str]) -> None:
    if not references or not set(references) <= allowed:
        raise ValueError("claim lacks valid event evidence")


def validate_opportunity(
    opportunity: OpportunityHypothesis, theme: IntelligenceTheme
) -> None:
    """Require an accepted problem and evidence; forbid unsupported market claims."""
    fields = (
        opportunity.problem_zh,
        opportunity.current_solution_zh,
        opportunity.gap_zh,
        opportunity.ai_leverage_zh,
        opportunity.potential_product_zh,
        opportunity.next_validation_step_zh,
    )
    for index, value in enumerate(fields):
        _nonempty_zh(value, f"opportunity field {index}")
    if opportunity.confidence not in _CONFIDENCE:
        raise ValueError("invalid opportunity confidence")
    if not opportunity.who_has_it_zh or not opportunity.potential_buyer_zh:
        raise ValueError("opportunity requires users and buyers")
    accepted = {
        (item.problem_zh, frozenset(item.evidence_event_ids))
        for item in theme.problem_signals
    }
    key = (opportunity.problem_zh, frozenset(opportunity.evidence_event_ids))
    if key not in accepted:
        raise ValueError("opportunity is not grounded in an accepted problem")
    _validate_refs(opportunity.evidence_event_ids, set(theme.event_ids))
    prohibited = re.compile(r"市场规模|定价|愿意付费|产品市场契合|已经验证")
    if any(prohibited.search(value) for value in fields):
        raise ValueError("unsupported commercial validation claim")


def group_related_events(
    events: Sequence[SynthesisEvent],
) -> list[tuple[SynthesisEvent, ...]]:
    """Group only explicit compatible mechanisms with overlapping semantic anchors."""
    groups: list[list[SynthesisEvent]] = []
    for item in sorted(events, key=lambda candidate: candidate.event.id):
        matched = next((group for group in groups if _related(item, group[0])), None)
        if matched is None:
            groups.append([item])
        else:
            matched.append(item)
    return [tuple(group) for group in groups]


def _related(left: SynthesisEvent, right: SynthesisEvent) -> bool:
    left_key, right_key = (
        left.theme_key.casefold().strip(),
        right.theme_key.casefold().strip(),
    )
    if left_key or right_key:
        return len(left_key) >= 5 and left_key == right_key
    if (
        not left.mechanism.strip()
        or left.mechanism.casefold() != right.mechanism.casefold()
    ):
        return False
    entity_overlap = set(map(str.casefold, left.principal_entities)) & set(
        map(str.casefold, right.principal_entities)
    )
    actor_overlap = set(map(str.casefold, left.affected_actors)) & set(
        map(str.casefold, right.affected_actors)
    )
    geography_overlap = set(map(str.casefold, left.geographies)) & set(
        map(str.casefold, right.geographies)
    )
    return bool(entity_overlap and (actor_overlap or geography_overlap))


def classify_change(
    current: Sequence[SynthesisEvent],
    history: Sequence[HistoricalTheme],
    reporting_date: str,
) -> ChangeState:
    """Classify against up to 90 valid days without counting syndicated repetition."""
    current_date = date.fromisoformat(reporting_date)
    valid = [
        item
        for item in history
        if item.status in {"complete", "partial"}
        and (current_date - date.fromisoformat(item.reporting_date)).days > 0
    ]
    valid_dates = sorted({item.reporting_date for item in valid}, reverse=True)[:90]
    valid = [item for item in valid if item.reporting_date in valid_dates]
    if not valid:
        return "insufficient_history"
    theme_id = _identity_for_group(current)
    matching = [item for item in valid if item.theme_id == theme_id]
    if not matching:
        return "new"
    current_directions = {item.direction for item in current if item.direction}
    old_directions = {item.direction for item in matching if item.direction}
    if (
        current_directions
        and old_directions
        and current_directions.isdisjoint(old_directions)
    ):
        return "turning"
    developments = {item.development_id for item in current if item.development_id}
    old_developments = {value for item in matching for value in item.development_ids}
    new_development = bool(developments - old_developments)
    if not new_development:
        return "unchanged"
    current_metrics = _metrics(current)
    recent_dates = set(valid_dates[:7])
    baseline_dates = set(valid_dates[7:30])
    long_dates = set(valid_dates[30:90])
    recent = [item for item in matching if item.reporting_date in recent_dates]
    baseline = [item for item in matching if item.reporting_date in baseline_dates]
    long_baseline = [item for item in matching if item.reporting_date in long_dates]
    # Acceleration requires sustained growth across all populated windows.
    if (
        recent
        and baseline
        and long_baseline
        and any(
            current_metrics[key]
            > _window_peak(recent, key)
            > _window_peak(baseline, key)
            > _window_peak(long_baseline, key)
            for key in current_metrics
        )
    ):
        return "accelerating"
    return "continuing"


def _identity_for_group(items: Sequence[SynthesisEvent]) -> str:
    keys = {
        item.theme_key.casefold().strip() for item in items if item.theme_key.strip()
    }
    if keys:
        if len(keys) != 1 or len(keys) != len(
            {item.theme_key.casefold().strip() for item in items}
        ):
            raise ValueError(
                "group contains missing or conflicting explicit theme keys"
            )
        key = next(iter(keys))
        if len(key) < 5:
            raise ValueError("explicit theme key is too short")
        return "theme_" + hashlib.sha256(("theme-key|" + key).encode()).hexdigest()[:16]

    def shared(attribute: str) -> set[str]:
        values = [
            {
                value.casefold()
                for value in cast(tuple[str, ...], getattr(item, attribute))
            }
            for item in items
        ]
        return set.intersection(*values)

    return stable_theme_id(
        shared("principal_entities"),
        shared("affected_actors"),
        shared("geographies"),
        items[0].mechanism,
    )


def _metrics(items: Sequence[SynthesisEvent]) -> dict[str, int]:
    return {
        "chains": len(
            {value for item in items for value in item.evidentiary_chain_ids}
        ),
        "geographies": len({value for item in items for value in item.geographies}),
        "industries": len({value for item in items for value in item.industries}),
        "actors": len({value for item in items for value in item.affected_actors}),
        "events": len({item.event.id for item in items}),
    }


def _history_metric(item: HistoricalTheme, key: str) -> int:
    values: Mapping[str, Sequence[str]] = {
        "chains": item.evidentiary_chain_ids,
        "geographies": item.geographies,
        "industries": item.industries,
        "actors": item.affected_actors,
        "events": item.development_ids,
    }
    return len(set(values[key]))


def _window_peak(items: Sequence[HistoricalTheme], key: str) -> int:
    return max(_history_metric(item, key) for item in items)


def parse_proposed_theme(payload: Mapping[str, object]) -> IntelligenceTheme:
    """Parse injectable content; validation remains a separate required gate."""

    def strings(name: str) -> tuple[str, ...]:
        value = payload.get(name, ())
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise ValueError(f"{name} must be a string list")
        return tuple(value)

    evidence = tuple(
        ThemeEvidence(str(item["event_id"]), str(item["source_name"]), str(item["url"]))
        for item in _dict_list(payload, "evidence")
    )
    impacts = tuple(
        ImpactLink(
            str(item["cause_zh"]),
            str(item["mechanism_zh"]),
            _item_strings(item, "affected_actors_zh"),
            str(item["effect_zh"]),
            cast(Confidence, item["confidence"]),
            _item_strings(item, "evidence_event_ids"),
        )
        for item in _dict_list(payload, "impact_chain")
    )
    problems = tuple(
        ProblemSignal(
            str(item["problem_zh"]),
            _item_strings(item, "who_has_it_zh"),
            cast(ProblemType, item["type"]),
            _item_strings(item, "evidence_event_ids"),
        )
        for item in _dict_list(payload, "problem_signals")
    )
    return IntelligenceTheme(
        str(payload["id"]),
        str(payload["reporting_date"]),
        str(payload["title_zh"]),
        str(payload["thesis_zh"]),
        strings("lanes"),
        strings("event_ids"),
        evidence,
        cast(ChangeState, payload["change_state"]),
        str(payload["change_summary_zh"]),
        impacts,
        problems,
        strings("counter_evidence_zh"),
        strings("uncertainties_zh"),
        cast(Confidence, payload["confidence"]),
        int(cast(int, payload["score"])),
        str(payload["score_rationale_zh"]),
    )


def _dict_list(payload: Mapping[str, object], name: str) -> list[Mapping[str, object]]:
    value = payload.get(name, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{name} must be an object list")
    return cast(list[Mapping[str, object]], value)


def _item_strings(item: Mapping[str, object], name: str) -> tuple[str, ...]:
    value = item.get(name)
    if not isinstance(value, list) or not all(isinstance(part, str) for part in value):
        raise ValueError(f"{name} must be a string list")
    return tuple(value)


def build_fallback_theme(
    events: Sequence[SynthesisEvent], reporting_date: str
) -> IntelligenceTheme:
    """Produce a narrow, explicitly limited Chinese fallback from supplied evidence."""
    if not events:
        raise ValueError("cannot synthesize an empty event group")
    event_ids = tuple(item.event.id for item in events)
    evidence = tuple(source for item in events for source in item.evidence)
    title = f"{events[0].event.title}：需要继续核实影响"
    theme = IntelligenceTheme(
        _identity_for_group(events),
        reporting_date,
        title,
        "现有事件显示相关变化已经发生，但证据不足以支持更广泛的因果结论。",
        tuple(sorted({lane for item in events for lane in item.lanes})),
        event_ids,
        evidence,
        "insufficient_history",
        "缺少足够历史，暂不判断趋势。",
        (),
        (),
        (),
        ("当前为确定性后备分析，尚需更多独立证据。",),
        "medium" if len({source.source_name for source in evidence}) > 1 else "low",
        0,
        "尚未评分；仅保留有来源的窄范围事件分析。",
    )
    validate_theme(theme, event_ids)
    return theme


def score_theme(
    theme: IntelligenceTheme,
    *,
    material_change: int,
    expected_impact: int,
    user_relevance: int,
    breadth: int,
    novelty: int,
) -> IntelligenceTheme:
    """Apply specified weights and evidence/conflict/inference penalties."""
    for value in (material_change, expected_impact, user_relevance, breadth, novelty):
        if not 0 <= value <= 100:
            raise ValueError("score dimensions must be between 0 and 100")
    chains = {(item.event_id, item.url) for item in theme.evidence}
    evidence_strength = min(100, 35 + 25 * len(chains))
    penalty = (15 if len(chains) == 1 else 0) + (10 if theme.counter_evidence_zh else 0)
    penalty += 10 if theme.confidence == "low" else 0
    total = round(
        material_change * 0.25
        + expected_impact * 0.25
        + evidence_strength * 0.20
        + user_relevance * 0.15
        + breadth * 0.10
        + novelty * 0.05
        - penalty
    )
    score = max(0, min(100, total))
    rationale = (
        f"变化{material_change}，影响{expected_impact}，证据{evidence_strength}，"
        f"相关性{user_relevance}，广度{breadth}，新颖性{novelty}，扣分{penalty}。"
    )
    return replace(theme, score=score, score_rationale_zh=rationale)


def select_themes(
    themes: Sequence[IntelligenceTheme], *, minimum_score: int = 45
) -> list[IntelligenceTheme]:
    """Select three strongest changes plus one strong Singapore/Asia theme."""
    eligible = sorted(
        (
            item
            for item in themes
            if item.score >= minimum_score and item.change_state != "unchanged"
        ),
        key=lambda item: (-item.score, item.id),
    )
    selected = eligible[:3]
    asia = next(
        (
            item
            for item in eligible
            if item not in selected
            and any(
                lane.casefold() in {"singapore/asia", "singapore", "asia"}
                for lane in item.lanes
            )
        ),
        None,
    )
    if asia is not None:
        selected.append(asia)
    elif len(selected) < 4:
        selected.extend(item for item in eligible if item not in selected)
        selected = selected[:4]
    return selected


def choose_opportunity(
    proposals: Sequence[tuple[OpportunityHypothesis, IntelligenceTheme]],
) -> OpportunityHypothesis | None:
    """Return at most one valid hypothesis, preferring score deterministically."""
    accepted: list[tuple[int, str, OpportunityHypothesis]] = []
    for proposal, theme in proposals:
        try:
            validate_opportunity(proposal, theme)
        except ValueError:
            continue
        accepted.append((theme.score, theme.id, proposal))
    return max(accepted, key=lambda item: (item[0], item[1]))[2] if accepted else None


def group_by_theme_id(
    events: Sequence[SynthesisEvent],
) -> Mapping[str, tuple[SynthesisEvent, ...]]:
    """Small convenience for callers persisting deterministic candidate groups."""
    result: defaultdict[str, list[SynthesisEvent]] = defaultdict(list)
    for group in group_related_events(events):
        result[_identity_for_group(group)].extend(group)
    return {key: tuple(value) for key, value in result.items()}
