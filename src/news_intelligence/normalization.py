"""Normalize collected entries and classify deterministic duplicates."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from news_intelligence.ingestion import CollectedArticle

ArticleStatus = Literal["accepted", "duplicate", "rejected"]
_TRACKING_PARAMETERS = {"fbclid", "gclid", "dclid", "msclkid", "ref"}
_SOURCE_SEPARATOR = re.compile(r"[^a-z0-9]+")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Article:
    """Normalized Article record defined by the product specification."""

    id: str
    title: str
    source_id: str
    source_name: str
    url: str
    canonical_url: str
    published_at: str
    collected_at: str
    language: str | None
    country: str | None
    topics: list[str]
    feed_summary: str | None
    text: str | None
    content_hash: str
    status: ArticleStatus
    rejection_reason: str | None


def normalize_text(value: str) -> str:
    """Normalize Unicode and collapse all whitespace."""
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value)).strip()


def normalize_source_id(value: str) -> str:
    """Turn a configured source identifier into a stable lowercase slug."""
    return _SOURCE_SEPARATOR.sub("-", normalize_text(value).casefold()).strip("-")


def canonicalize_url(value: str) -> str:
    """Normalize an HTTP URL and discard common tracking data."""
    try:
        parsed = urlsplit(normalize_text(value))
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return ""
    if parsed.scheme.casefold() not in {"http", "https"} or not hostname:
        return ""
    scheme = parsed.scheme.casefold()
    hostname = hostname.casefold()
    netloc = hostname
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{hostname}:{port}"
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.casefold().startswith("utm_")
            and key.casefold() not in _TRACKING_PARAMETERS
        )
    )
    path = parsed.path or "/"
    return urlunsplit((scheme, netloc, path, query, ""))


def _timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(normalize_text(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("publication time must include a timezone")
    return parsed.astimezone(UTC).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _content(article: CollectedArticle) -> str:
    # Ingestion does not yet retrieve article bodies; summaries are the available text.
    return normalize_text(article.feed_summary or "")


def _base_article(raw: CollectedArticle) -> Article:
    title = normalize_text(raw.title)
    canonical_url = canonicalize_url(raw.url)
    source_id = normalize_source_id(raw.source_id)
    content = _content(raw)
    reasons: list[str] = []
    if not title:
        reasons.append("missing usable title")
    if not canonical_url:
        reasons.append("missing usable URL")
    try:
        published_at = _timestamp(raw.published_at)
    except ValueError:
        published_at = normalize_text(raw.published_at)
        reasons.append("missing usable publication time")
    try:
        collected_at = _timestamp(raw.collected_at)
    except ValueError:
        collected_at = normalize_text(raw.collected_at)
    identity = canonical_url or f"rejected:{source_id}:{title}:{published_at}"
    return Article(
        id=_hash(identity),
        title=title,
        source_id=source_id,
        source_name=normalize_text(raw.source_name),
        url=normalize_text(raw.url),
        canonical_url=canonical_url,
        published_at=published_at,
        collected_at=collected_at,
        language=normalize_text(raw.language) if raw.language else None,
        country=None,
        topics=[],
        feed_summary=content or None,
        text=None,
        content_hash=_hash(content) if content else "",
        status="rejected" if reasons else "accepted",
        rejection_reason="; ".join(reasons) or None,
    )


def normalize_and_deduplicate(entries: list[CollectedArticle]) -> list[Article]:
    """Return one classified Article for every input entry, in input order."""
    articles = [_base_article(entry) for entry in entries]
    accepted: list[int] = []
    for index, article in enumerate(articles):
        if article.status == "rejected":
            continue
        published = datetime.fromisoformat(article.published_at)
        reason: str | None = None
        for prior_index in accepted:
            prior = articles[prior_index]
            if article.canonical_url == prior.canonical_url:
                reason = f"duplicate canonical URL of {prior.id}"
                break
            prior_published = datetime.fromisoformat(prior.published_at)
            within_48_hours = abs(published - prior_published) <= timedelta(hours=48)
            if within_48_hours and article.title.casefold() == prior.title.casefold():
                reason = f"duplicate normalized title of {prior.id}"
                break
            if article.feed_summary and prior.feed_summary:
                exact = article.content_hash == prior.content_hash
                near = (
                    min(len(article.feed_summary), len(prior.feed_summary)) >= 40
                    and SequenceMatcher(
                        None,
                        article.feed_summary.casefold(),
                        prior.feed_summary.casefold(),
                    ).ratio()
                    >= 0.95
                )
                if exact or near:
                    reason = f"syndicated content copy of {prior.id}"
                    break
        if reason:
            articles[index] = replace(
                article, status="duplicate", rejection_reason=reason
            )
        else:
            accepted.append(index)
    return articles


def articles_json(articles: list[Article]) -> list[dict[str, object]]:
    """Convert normalized articles into JSON-compatible dictionaries."""
    return [asdict(article) for article in articles]
