"""Conservative, deterministic grouping of accepted articles into events."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from news_intelligence.archive import atomic_write_json
from news_intelligence.normalization import Article, normalize_text

AmbiguousPairReasoner = Callable[[Article, "Event"], bool]
_WORDS = re.compile(r"[\w'-]+", re.UNICODE)
_STOP = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "the",
    "to",
    "with",
    "after",
    "amid",
    "new",
    "says",
}
_ACTIONS = {
    "acquire",
    "acquires",
    "acquired",
    "announce",
    "announces",
    "announced",
    "approve",
    "approves",
    "approved",
    "ban",
    "bans",
    "banned",
    "cut",
    "cuts",
    "launch",
    "launches",
    "launched",
    "raise",
    "raises",
    "raised",
    "resign",
    "resigns",
    "resigned",
    "sign",
    "signs",
    "signed",
    "sue",
    "sues",
    "sued",
}


@dataclass(frozen=True)
class Importance:
    impact: int = 0
    breadth: int = 0
    novelty: int = 0
    momentum: int = 0
    source_quality: int = 0
    user_relevance: int = 0
    total: int = 0
    rationale: str = "Not scored"


@dataclass(frozen=True)
class Event:
    """Stable Event record defined by the product specification."""

    id: str
    title: str
    summary: str
    first_seen_at: str
    last_seen_at: str
    article_ids: list[str]
    distinct_source_count: int
    countries: list[str]
    topics: list[str]
    entities: list[str]
    importance: Importance
    confidence: str


def _tokens(article: Article) -> set[str]:
    text = normalize_text(f"{article.title} {article.feed_summary or ''}").casefold()
    return {
        word for word in _WORDS.findall(text) if len(word) > 2 and word not in _STOP
    }


def _entities(article: Article) -> set[str]:
    text = f"{article.title} {article.feed_summary or ''}"
    names = {item.casefold() for item in re.findall(r"\b[A-Z][\w-]+", text)}
    return names | ({article.country.casefold()} if article.country else set())


def _actions(article: Article) -> set[str]:
    return _tokens(article) & _ACTIONS


def _representative(event: Event, lookup: dict[str, Article]) -> Article:
    return lookup[event.article_ids[0]]


def _compatibility(article: Article, event: Event, lookup: dict[str, Article]) -> str:
    prior = _representative(event, lookup)
    if abs(
        datetime.fromisoformat(article.published_at)
        - datetime.fromisoformat(prior.published_at)
    ) > timedelta(hours=48):
        return "separate"
    left, right = _tokens(article), _tokens(prior)
    overlap = len(left & right) / max(1, min(len(left), len(right)))
    entity_overlap = bool(_entities(article) & _entities(prior))
    actions_left, actions_right = _actions(article), _actions(prior)
    action_conflict = bool(
        actions_left and actions_right and not actions_left & actions_right
    )
    topic_conflict = bool(
        article.topics and prior.topics and not set(article.topics) & set(prior.topics)
    )
    place_conflict = bool(
        article.country and prior.country and article.country != prior.country
    )
    if action_conflict or topic_conflict or place_conflict:
        return "separate"
    if overlap >= 0.80 and entity_overlap:
        return "match"
    if overlap >= 0.45 and entity_overlap:
        return "ambiguous"
    return "separate"


def _event_id(article_id: str) -> str:
    return "evt_" + hashlib.sha256(article_id.encode()).hexdigest()[:16]


def _build_event(articles: Sequence[Article], *, event_id: str) -> Event:
    ordered = sorted(articles, key=lambda item: (item.published_at, item.id))
    entities = set().union(*(_entities(item) for item in ordered))
    summaries = [item.feed_summary for item in ordered if item.feed_summary]
    return Event(
        id=event_id,
        title=ordered[0].title,
        summary=summaries[0] if summaries else ordered[0].title,
        first_seen_at=ordered[0].published_at,
        last_seen_at=ordered[-1].published_at,
        article_ids=[item.id for item in ordered],
        distinct_source_count=len({item.source_id for item in ordered}),
        countries=sorted({item.country for item in ordered if item.country}),
        topics=sorted({topic for item in ordered for topic in item.topics}),
        entities=sorted(entities),
        importance=Importance(),
        confidence="high" if len({item.source_id for item in ordered}) > 1 else "low",
    )


def cluster_articles(
    articles: Sequence[Article],
    *,
    prior_events: Sequence[Event] = (),
    reasoner: AmbiguousPairReasoner | None = None,
) -> list[Event]:
    """Cluster accepted articles; ambiguous pairs split unless a reasoner approves."""
    accepted = sorted(
        (item for item in articles if item.status == "accepted"),
        key=lambda item: (item.published_at, item.id),
    )
    lookup = {item.id: item for item in accepted}
    prior_by_article = {
        article_id: event.id
        for event in prior_events
        for article_id in event.article_ids
    }
    groups: list[tuple[str, list[Article]]] = []
    for article in accepted:
        stable_id = prior_by_article.get(article.id)
        if stable_id is not None:
            group = next((item for item in groups if item[0] == stable_id), None)
            if group is None:
                groups.append((stable_id, [article]))
            else:
                group[1].append(article)
            continue
        matched: tuple[str, list[Article]] | None = None
        for group in groups:
            candidate = _build_event(group[1], event_id=group[0])
            verdict = _compatibility(article, candidate, lookup)
            if verdict == "match" or (
                verdict == "ambiguous"
                and reasoner is not None
                and reasoner(article, candidate)
            ):
                matched = group
                break
        if matched is None:
            groups.append((_event_id(article.id), [article]))
        else:
            matched[1].append(article)
        lookup[article.id] = article
    return [_build_event(items, event_id=event_id) for event_id, items in groups]


def archive_events(
    data_dir: Path, reporting_date: str, events: Sequence[Event]
) -> Path:
    """Persist the dated private Event archive atomically."""
    path = data_dir / "events" / f"{reporting_date}.json"
    atomic_write_json(path, [asdict(event) for event in events])
    return path
