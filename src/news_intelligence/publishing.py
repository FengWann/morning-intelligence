"""Build a secret-safe static archive from a verified brief."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Literal

from news_intelligence.briefing import BriefInput, GeneratedBrief

PublishStatus = Literal["complete", "partial"]
PUBLIC_PATTERNS = (
    "index.html",
    "latest.json",
    "briefs/*.md",
    "briefs/*.json",
)
_DATE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
_PROHIBITED = (
    re.compile(r"(?i)\b(?:api[_-]?key|password|client[_-]?secret)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\b(?:bearer|authorization:)\s+\S+"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:file://|[A-Z]:\\|/Users/|/home/)"),
    re.compile(r"(?i)\b(?:internal prompt|processing log|private note)\b"),
    re.compile(r'(?i)"(?:raw_text|text|prompt|logs?|private_notes?)"\s*:'),
)


@dataclass(frozen=True)
class PublicSource:
    name: str
    url: str


@dataclass(frozen=True)
class PublicEvent:
    id: str
    title: str
    summary: str
    confidence: str
    sources: tuple[PublicSource, ...]


@dataclass(frozen=True)
class Publication:
    date: str
    status: PublishStatus
    brief_url: str
    speech_text: str
    generated_at: str
    events: tuple[PublicEvent, ...]


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _public_events(data: BriefInput) -> tuple[PublicEvent, ...]:
    return tuple(
        PublicEvent(
            item.ranked.event.id,
            item.ranked.event.title,
            item.ranked.event.summary,
            item.ranked.event.confidence,
            tuple(
                PublicSource(source.source_name, source.url) for source in item.evidence
            ),
        )
        for item in data.events
    )


def build_publication(
    data: BriefInput,
    brief: GeneratedBrief,
    *,
    status: PublishStatus,
    generated_at: datetime,
    base_url: str,
) -> Publication:
    """Build the allowlisted public contract without private article fields."""
    if not _DATE.fullmatch(data.reporting_date):
        raise ValueError("reporting date must use YYYY-MM-DD")
    if generated_at.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    root = base_url.rstrip("/")
    if not root.startswith("https://"):
        raise ValueError("base_url must use HTTPS")
    return Publication(
        data.reporting_date,
        status,
        f"{root}/briefs/{data.reporting_date}.md",
        brief.speech_text,
        generated_at.isoformat(),
        _public_events(data),
    )


def _allowed(relative: str) -> bool:
    path = PurePosixPath(relative)
    return any(path.match(pattern) for pattern in PUBLIC_PATTERNS)


def scan_public_files(
    files: Mapping[str, str], *, private_article_bodies: Sequence[str] = ()
) -> None:
    """Reject unsafe content or paths before anything reaches public/."""
    for relative, content in files.items():
        if not _allowed(relative) or ".." in PurePosixPath(relative).parts:
            raise ValueError(f"path is not on public allowlist: {relative}")
        for pattern in _PROHIBITED:
            if pattern.search(content):
                raise ValueError(f"unsafe public content in {relative}")
        compact = " ".join(content.split())
        for body in private_article_bodies:
            normalized_body = " ".join(body.split())
            if len(normalized_body) >= 100 and normalized_body in compact:
                raise ValueError(f"full article body in {relative}")


def _archive_index(dates: Sequence[str]) -> str:
    links = "\n".join(
        f'<li><a href="briefs/{date}.md">{date}</a></li>'
        for date in sorted(set(dates), reverse=True)
    )
    return (
        '<!doctype html>\n<meta charset="utf-8">\n'
        "<title>Morning Intelligence Brief</title>\n"
        "<h1>Morning Intelligence Brief</h1>\n<ul>\n"
        f"{links}\n</ul>\n"
    )


def _existing_dates(public_dir: Path) -> list[str]:
    briefs = public_dir / "briefs"
    if not briefs.exists():
        return []
    return [path.stem for path in briefs.glob("*.md") if _DATE.fullmatch(path.stem)]


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as stream:
            temporary = stream.name
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def publish(
    public_dir: Path,
    publication: Publication,
    markdown: str,
    *,
    private_article_bodies: Sequence[str] = (),
) -> tuple[Path, ...]:
    """Validate the complete site update, then atomically replace allowlisted files."""
    date = publication.date
    public_payload = asdict(publication)
    latest_payload = {
        key: public_payload[key]
        for key in ("date", "status", "brief_url", "speech_text", "generated_at")
    }
    files = {
        f"briefs/{date}.md": markdown,
        f"briefs/{date}.json": _json(public_payload),
        "latest.json": _json(latest_payload),
        "index.html": _archive_index([*_existing_dates(public_dir), date]),
    }
    scan_public_files(files, private_article_bodies=private_article_bodies)
    paths: list[Path] = []
    # latest.json is replaced last, so readers never see a pointer to absent files.
    for relative in sorted(files, key=lambda item: item == "latest.json"):
        target = public_dir / relative
        _atomic_write(target, files[relative])
        paths.append(target)
    return tuple(paths)


def validate_public_tree(public_dir: Path) -> None:
    """Ensure an existing site contains only explicitly allowed, safe files."""
    files = {
        path.relative_to(public_dir).as_posix(): path.read_text(encoding="utf-8")
        for path in public_dir.rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    }
    scan_public_files(files)
