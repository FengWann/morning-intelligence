"""Evidence-bound Chinese brief generation and editorial verification."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from news_intelligence.normalization import Article
from news_intelligence.ranking import CATEGORIES, RankedEvent

ClaimKind = Literal["fact", "attributed_claim", "analysis"]
Generator = Callable[["BriefInput"], "BriefDraft"]
_CLAIM_WORDS = re.compile(r"\b(?:claim(?:s|ed)?|says?|alleges?|denies?)\b", re.I)
_CJK = re.compile(r"[\u3400-\u9fff]")
_WORDS = re.compile(r"[A-Za-z0-9]+")


@dataclass(frozen=True)
class Evidence:
    article_id: str
    source_id: str
    source_name: str
    title: str
    summary: str
    url: str


@dataclass(frozen=True)
class BriefEvent:
    ranked: RankedEvent
    evidence: tuple[Evidence, ...]
    disputed: bool


@dataclass(frozen=True)
class BriefInput:
    reporting_date: str
    events: tuple[BriefEvent, ...]
    prior_events: tuple[dict[str, object], ...]
    insufficient_history: bool


@dataclass(frozen=True)
class Claim:
    text: str
    kind: ClaimKind
    event_id: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class BriefDraft:
    opening: str
    sections: Mapping[str, tuple[Claim, ...]]
    what_changed: tuple[Claim, ...]
    things_to_watch: tuple[Claim, ...]


@dataclass(frozen=True)
class GeneratedBrief:
    markdown: str
    speech_text: str
    estimated_seconds: int
    warnings: tuple[str, ...]


def _valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def build_input(
    reporting_date: str,
    selected: Sequence[RankedEvent],
    articles: Mapping[str, Article],
    archive_dir: Path,
) -> BriefInput:
    """Build the only data exposed to a deterministic or Codex generator."""
    prepared: list[BriefEvent] = []
    for item in selected:
        evidence = tuple(
            Evidence(
                article.id,
                article.source_id,
                article.source_name,
                article.title,
                article.feed_summary or article.title,
                article.canonical_url,
            )
            for article_id in item.event.article_ids
            if (article := articles.get(article_id)) is not None
            and _valid_url(article.canonical_url)
        )
        if not evidence:
            raise ValueError(f"event {item.event.id} has no valid evidence URL")
        disputed = item.category == "Politics" and any(
            _CLAIM_WORDS.search(f"{source.title} {source.summary}")
            for source in evidence
        )
        prepared.append(BriefEvent(item, evidence, disputed))

    histories: list[dict[str, object]] = []
    prior_paths = [
        path
        for path in sorted(archive_dir.glob("*.json"), reverse=True)
        if path.stem < reporting_date
    ][:7]
    for path in prior_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            histories.extend(item for item in payload if isinstance(item, dict))
    return BriefInput(
        reporting_date,
        tuple(prepared),
        tuple(histories),
        len(prior_paths) < 7,
    )


def deterministic_draft(data: BriefInput) -> BriefDraft:
    """Create a conservative no-API fallback containing no unsupported facts."""
    sections: dict[str, tuple[Claim, ...]] = {}
    for category in CATEGORIES:
        claims: list[Claim] = []
        for item in (
            event for event in data.events if event.ranked.category == category
        ):
            record = item.ranked.event
            ids = tuple(source.article_id for source in item.evidence)
            prefix = "据相关来源称，" if item.disputed else "已报道："
            kind: ClaimKind = "attributed_claim" if item.disputed else "fact"
            if item.disputed:
                claims.extend(
                    Claim(
                        f"{source.source_name}称：{source.summary}",
                        kind,
                        record.id,
                        (source.article_id,),
                    )
                    for source in item.evidence
                )
            else:
                claims.append(Claim(prefix + record.summary, kind, record.id, ids))
            claims.append(
                Claim(
                    "系统分析：该事件的重要性评分依据为" + record.importance.rationale,
                    "analysis",
                    record.id,
                    ids,
                )
            )
        sections[category] = tuple(claims)

    changed: tuple[Claim, ...]
    if data.insufficient_history:
        changed = ()
    else:
        prior_ids = {str(item.get("id", "")) for item in data.prior_events}
        changed = tuple(
            Claim(
                "与近七次记录相比，这是一个新出现的事件；这不等同于趋势。",
                "analysis",
                item.ranked.event.id,
                tuple(source.article_id for source in item.evidence),
            )
            for item in data.events
            if item.ranked.event.id not in prior_ids
        )
    watch = tuple(
        Claim(
            "后续关注是否出现新的独立来源或实质进展。",
            "analysis",
            item.ranked.event.id,
            tuple(source.article_id for source in item.evidence),
        )
        for item in data.events
    )
    return BriefDraft("早上好，以下是今日重要情报。", sections, changed, watch)


def estimate_speech_seconds(text: str) -> int:
    """Estimate Chinese system-speech duration at 180 spoken units/minute."""
    units = len(_CJK.findall(text)) + len(_WORDS.findall(text))
    return round(units / 180 * 60)


def _verify_claim(claim: Claim, event: BriefEvent) -> None:
    valid_ids = {item.article_id for item in event.evidence}
    if not claim.evidence_ids or not set(claim.evidence_ids) <= valid_ids:
        raise ValueError(f"claim for {claim.event_id} exceeds supplied evidence")
    if event.disputed and claim.kind == "fact":
        raise ValueError(f"disputed event {claim.event_id} cannot be stated as fact")


def render_brief(
    data: BriefInput,
    draft: BriefDraft,
    *,
    minimum_seconds: int = 600,
    maximum_seconds: int = 900,
) -> GeneratedBrief:
    """Verify a draft and render Markdown plus URL-free speech text."""
    by_id = {item.ranked.event.id: item for item in data.events}
    all_claims = (
        [claim for claims in draft.sections.values() for claim in claims]
        + list(draft.what_changed)
        + list(draft.things_to_watch)
    )
    for claim in all_claims:
        event = by_id.get(claim.event_id)
        if event is None:
            raise ValueError(f"unknown event in claim: {claim.event_id}")
        _verify_claim(claim, event)

    for event in data.events:
        sources = {item.source_id for item in event.evidence}
        if event.disputed and len(sources) >= 2:
            attributed = [
                claim
                for claim in all_claims
                if claim.event_id == event.ranked.event.id
                and claim.kind == "attributed_claim"
            ]
            if not attributed:
                raise ValueError("disputed accounts must remain attributed")

    warnings = tuple(
        f"单一来源警告：{item.ranked.event.title}"
        for item in data.events
        if item.disputed and len({source.source_id for source in item.evidence}) < 2
    )
    if data.insufficient_history:
        warnings += ("历史数据不足：What Changed? 暂不判断趋势。",)

    labels = {
        "fact": "已确认事实",
        "attributed_claim": "各方主张",
        "analysis": "系统分析",
    }
    markdown_parts = [
        f"# Morning Intelligence Brief — {data.reporting_date}",
        "",
        draft.opening,
    ]
    speech_parts = [draft.opening]
    for category in CATEGORIES:
        markdown_parts += ["", f"## {category}"]
        speech_parts.append(category)
        for claim in draft.sections.get(category, ()):
            markdown_parts.append(f"- **{labels[claim.kind]}：** {claim.text}")
            speech_parts.append(f"{labels[claim.kind]}。{claim.text}")
    markdown_parts += ["", "## What Changed?"]
    speech_parts.append("What Changed")
    if data.insufficient_history:
        note = "历史数据不足，今天不作趋势判断。"
        markdown_parts.append(note)
        speech_parts.append(note)
    for claim in draft.what_changed:
        markdown_parts.append(f"- **{labels[claim.kind]}：** {claim.text}")
        speech_parts.append(f"{labels[claim.kind]}。{claim.text}")
    markdown_parts += ["", "## Things to Watch"]
    speech_parts.append("Things to Watch")
    for claim in draft.things_to_watch:
        markdown_parts.append(f"- {claim.text}")
        speech_parts.append(claim.text)
    markdown_parts += ["", "## Sources"]
    for event in data.events:
        for source in event.evidence:
            markdown_parts.append(
                f"- [{source.source_name}]({source.url}) — {source.title}"
            )
    if warnings:
        markdown_parts += ["", "## Warnings", *(f"- {item}" for item in warnings)]
        speech_parts.extend(warnings)
    speech = "\n".join(speech_parts)
    if re.search(r"https?://|\[[^]]+\]\([^)]*\)", speech):
        raise ValueError("speech_text contains URL or Markdown link mechanics")
    seconds = estimate_speech_seconds(speech)
    if not minimum_seconds <= seconds <= maximum_seconds:
        raise ValueError(f"estimated speech duration {seconds}s is outside 600-900s")
    return GeneratedBrief("\n".join(markdown_parts) + "\n", speech, seconds, warnings)


def generate_brief(
    data: BriefInput,
    *,
    generator: Generator = deterministic_draft,
    minimum_seconds: int = 600,
    maximum_seconds: int = 900,
) -> GeneratedBrief:
    """Generation seam for scheduled Codex reasoning with common verification."""
    return render_brief(
        data,
        generator(data),
        minimum_seconds=minimum_seconds,
        maximum_seconds=maximum_seconds,
    )
