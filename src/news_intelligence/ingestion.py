"""Collect recent news from configured RSS/Atom feeds and GDELT."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Literal, cast
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

SourceKind = Literal["rss", "gdelt"]
Lane = Literal["politics", "business", "ai_technology", "singapore_asia", "global"]
Fetcher = Callable[[str], bytes]


@dataclass(frozen=True)
class Source:
    """Validated collection source."""

    id: str
    name: str
    kind: SourceKind
    url: str
    lane: Lane
    language: str | None = None
    query: str | None = None


@dataclass(frozen=True)
class CollectedArticle:
    """Raw article metadata preserved by ingestion."""

    source_id: str
    source_name: str
    title: str
    url: str
    published_at: str
    feed_summary: str | None
    language: str | None
    collected_at: str


@dataclass(frozen=True)
class SourceResult:
    """Outcome for one independently collected source."""

    source_id: str
    status: Literal["success", "failure"]
    article_count: int
    error: str | None = None


@dataclass(frozen=True)
class CollectionResult:
    """Structured aggregate collection result."""

    articles: list[CollectedArticle]
    sources: list[SourceResult]
    article_count: int
    success_count: int
    failure_count: int


def load_sources(path: Path) -> list[Source]:
    """Load and validate the source configuration JSON."""
    value = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(value, dict) or not isinstance(value.get("sources"), list):
        raise ValueError("source config must contain a sources list")
    sources: list[Source] = []
    seen: set[str] = set()
    for raw in cast(list[object], value["sources"]):
        if not isinstance(raw, dict):
            raise ValueError("each source must be an object")
        item = cast(dict[str, object], raw)
        required = ("id", "name", "kind", "url", "lane")
        if any(not isinstance(item.get(key), str) or not item[key] for key in required):
            raise ValueError(
                "source id, name, kind, url, and lane are required strings"
            )
        source_id = cast(str, item["id"])
        kind = item["kind"]
        lane = item["lane"]
        if source_id in seen:
            raise ValueError(f"duplicate source id: {source_id}")
        if kind not in ("rss", "gdelt") or lane not in (
            "politics",
            "business",
            "ai_technology",
            "singapore_asia",
            "global",
        ):
            raise ValueError(f"invalid source kind or lane: {source_id}")
        query = item.get("query")
        if kind == "gdelt" and (not isinstance(query, str) or not query):
            raise ValueError(f"GDELT source requires a query: {source_id}")
        language = item.get("language")
        if language is not None and not isinstance(language, str):
            raise ValueError(f"invalid language: {source_id}")
        sources.append(
            Source(
                source_id,
                cast(str, item["name"]),
                cast(SourceKind, kind),
                cast(str, item["url"]),
                cast(Lane, lane),
                language,
                cast(str | None, query),
            )
        )
        seen.add(source_id)
    return sources


def fetch_url(url: str) -> bytes:
    """Fetch one public endpoint with a bounded timeout."""
    request = Request(url, headers={"User-Agent": "news-intelligence/0.1"})
    with urlopen(request, timeout=20) as response:  # noqa: S310 - configured HTTPS sources
        return cast(bytes, response.read())


def _iso(value: str) -> datetime:
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed = parsedate_to_datetime(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _text(element: ElementTree.Element, names: Sequence[str]) -> str | None:
    for child in element.iter():
        if child.tag.rsplit("}", 1)[-1] in names and child.text and child.text.strip():
            return child.text.strip()
    return None


def parse_feed(
    data: bytes, source: Source, since: datetime, now: datetime
) -> list[CollectedArticle]:
    """Parse RSS 2.0 or Atom entries published within the collection window."""
    root = ElementTree.fromstring(data)
    articles: list[CollectedArticle] = []
    for entry in root.iter():
        if entry.tag.rsplit("}", 1)[-1] not in ("item", "entry"):
            continue
        title = _text(entry, ("title",))
        published = _text(entry, ("pubDate", "published", "updated"))
        link = _text(entry, ("link",))
        if link is None:
            link_node = next(
                (
                    node
                    for node in entry
                    if node.tag.rsplit("}", 1)[-1] == "link" and node.get("href")
                ),
                None,
            )
            link = link_node.get("href") if link_node is not None else None
        if not title or not link or not published:
            continue
        published_at = _iso(published)
        if published_at < since or published_at > now:
            continue
        articles.append(
            CollectedArticle(
                source.id,
                source.name,
                title,
                link,
                published_at.isoformat(),
                _text(entry, ("description", "summary", "content")),
                source.language,
                now.isoformat(),
            )
        )
    return articles


def parse_gdelt(
    data: bytes, source: Source, since: datetime, now: datetime
) -> list[CollectedArticle]:
    """Parse GDELT DOC API JSON articles within the collection window."""
    payload = cast(object, json.loads(data))
    if not isinstance(payload, dict) or not isinstance(payload.get("articles"), list):
        raise ValueError("GDELT response must contain an articles list")
    articles: list[CollectedArticle] = []
    for raw in cast(list[object], payload["articles"]):
        if not isinstance(raw, dict):
            continue
        item = cast(Mapping[str, object], raw)
        title, url, seen = item.get("title"), item.get("url"), item.get("seendate")
        if not all(isinstance(value, str) and value for value in (title, url, seen)):
            continue
        published_at = datetime.strptime(cast(str, seen), "%Y%m%dT%H%M%SZ").replace(
            tzinfo=UTC
        )
        if since <= published_at <= now:
            language = item.get("language")
            articles.append(
                CollectedArticle(
                    source.id,
                    source.name,
                    cast(str, title),
                    cast(str, url),
                    published_at.isoformat(),
                    None,
                    language if isinstance(language, str) else source.language,
                    now.isoformat(),
                )
            )
    return articles


def collect(
    sources: Sequence[Source],
    now: datetime,
    fetcher: Fetcher = fetch_url,
    hours: int = 24,
) -> CollectionResult:
    """Collect every source independently, preserving individual failures."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(UTC)
    since = now - timedelta(hours=hours)
    articles: list[CollectedArticle] = []
    results: list[SourceResult] = []
    for source in sources:
        try:
            url = source.url
            if source.kind == "gdelt":
                parameters = {
                    "query": source.query,
                    "mode": "artlist",
                    "format": "json",
                    "maxrecords": 250,
                    "startdatetime": since.strftime("%Y%m%d%H%M%S"),
                    "enddatetime": now.strftime("%Y%m%d%H%M%S"),
                }
                url = f"{url}?{urlencode(parameters)}"
            found = (
                parse_feed(fetcher(url), source, since, now)
                if source.kind == "rss"
                else parse_gdelt(fetcher(url), source, since, now)
            )
            articles.extend(found)
            results.append(SourceResult(source.id, "success", len(found)))
        except (OSError, ValueError, ElementTree.ParseError) as exc:
            results.append(SourceResult(source.id, "failure", 0, str(exc)))
    successes = sum(result.status == "success" for result in results)
    return CollectionResult(
        articles, results, len(articles), successes, len(results) - successes
    )


def result_json(result: CollectionResult) -> str:
    """Serialize a collection result for CLI and downstream modules."""
    return json.dumps(asdict(result), ensure_ascii=False, indent=2)
