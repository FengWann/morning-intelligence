"""Deterministic, explainable event scoring and balanced brief selection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal

from news_intelligence.clustering import Event, Importance
from news_intelligence.normalization import Article

Category = Literal["Politics", "Business", "AI/Technology", "Singapore/Asia"]
CATEGORIES: tuple[Category, ...] = (
    "Politics",
    "Business",
    "AI/Technology",
    "Singapore/Asia",
)
WEIGHTS = {
    "impact": 0.30,
    "breadth": 0.20,
    "novelty": 0.15,
    "momentum": 0.15,
    "source_quality": 0.10,
    "user_relevance": 0.10,
}
_AUTHORITATIVE = {
    "ap",
    "bbc",
    "cna",
    "reuters",
    "sg-gov",
    "singapore-government",
}
_KEYWORDS: dict[Category, frozenset[str]] = {
    "Politics": frozenset(
        {"election", "government", "minister", "policy", "regulation", "war"}
    ),
    "Business": frozenset(
        {"business", "company", "economy", "finance", "market", "trade"}
    ),
    "AI/Technology": frozenset(
        {"ai", "artificial intelligence", "model", "software", "technology"}
    ),
    "Singapore/Asia": frozenset(
        {"asia", "asean", "china", "india", "japan", "singapore"}
    ),
}


@dataclass(frozen=True)
class RankedEvent:
    """A scored event with editorial metadata used by brief generation."""

    event: Event
    category: Category
    labels: tuple[str, ...]
    estimated_seconds: int


def _cap(value: int) -> int:
    return max(0, min(100, value))


def _category(event: Event) -> Category:
    text = " ".join((event.title, event.summary, *event.topics)).casefold()
    scores = {
        category: sum(keyword in text for keyword in keywords)
        for category, keywords in _KEYWORDS.items()
    }
    if "SG" in event.countries or "singapore" in text:
        scores["Singapore/Asia"] += 2
    return max(CATEGORIES, key=lambda item: (scores[item], -CATEGORIES.index(item)))


def score_event(event: Event, articles: Mapping[str, Article]) -> RankedEvent:
    """Score one event from retained evidence without model calls."""
    evidence = [articles[item] for item in event.article_ids if item in articles]
    category = _category(event)
    sources = {item.source_id for item in evidence}
    independent = len(sources)
    authoritative = len(sources & _AUTHORITATIVE)
    impact = _cap(35 + len(event.entities) * 8 + min(independent, 3) * 8)
    breadth = _cap(25 + len(event.countries) * 20 + (20 if independent >= 3 else 0))
    novelty = _cap(55 + (15 if independent else 0))
    momentum = _cap(25 + min(independent, 4) * 18)
    source_quality = _cap(20 + authoritative * 25 + min(independent, 3) * 10)
    user_relevance = 75 if category in CATEGORIES else 25
    values = {
        "impact": impact,
        "breadth": breadth,
        "novelty": novelty,
        "momentum": momentum,
        "source_quality": source_quality,
        "user_relevance": user_relevance,
    }
    total = round(sum(values[name] * weight for name, weight in WEIGHTS.items()))
    rationale = "; ".join(
        (
            (
                f"impact={impact} ({len(event.entities)} entities, "
                f"{independent} independent sources)"
            ),
            f"breadth={breadth} ({len(event.countries)} countries)",
            f"novelty={novelty} (new candidate event)",
            f"momentum={momentum} ({independent} independent sources)",
            f"source_quality={source_quality} ({authoritative} authoritative sources)",
            f"user_relevance={user_relevance} ({category})",
            f"total={total} (weighted score)",
        )
    )
    confidence = "high" if independent >= 2 and authoritative else "medium"
    labels: list[str] = []
    if independent <= 1:
        confidence = "low"
        labels.append("single-source")
    if confidence == "low":
        labels.append("low-confidence")
    scored = replace(
        event,
        importance=Importance(**values, total=total, rationale=rationale),
        confidence=confidence,
    )
    # Two minutes reserves room for context, transitions and non-event sections.
    return RankedEvent(scored, category, tuple(labels), estimated_seconds=120)


def rank_events(
    events: Sequence[Event], articles: Mapping[str, Article]
) -> list[RankedEvent]:
    """Return all candidates in stable descending score order."""
    return sorted(
        (score_event(event, articles) for event in events),
        key=lambda item: (-item.event.importance.total, item.event.id),
    )


def select_events(
    ranked: Sequence[RankedEvent],
    *,
    minimum_score: int = 45,
    max_spoken_seconds: int = 900,
) -> list[RankedEvent]:
    """Round-robin strong candidates across categories within the speech budget."""
    queues = {
        category: [
            item
            for item in ranked
            if item.category == category
            and item.event.importance.total >= minimum_score
        ]
        for category in CATEGORIES
    }
    selected: list[RankedEvent] = []
    seen: set[str] = set()
    used = 0
    while any(queues.values()):
        added = False
        for category in CATEGORIES:
            while queues[category]:
                item = queues[category].pop(0)
                if item.event.id in seen:
                    continue
                if used + item.estimated_seconds > max_spoken_seconds:
                    return selected
                selected.append(item)
                seen.add(item.event.id)
                used += item.estimated_seconds
                added = True
                break
        if not added:
            break
    return selected
