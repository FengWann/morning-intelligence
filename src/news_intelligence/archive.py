"""Private, idempotent daily archives with interruption-safe writes."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from news_intelligence.ingestion import SourceResult
from news_intelligence.normalization import Article, articles_json

RunStatus = Literal["running", "complete", "partial", "failed", "missed"]
Replace = Callable[[str, str], None]
SINGAPORE = ZoneInfo("Asia/Singapore")
_SECRET_FIELD = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization)(\s*[=:]\s*)([^\s&,;]+)"
)
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_QUERY_SECRET = re.compile(r"(?i)([?&](?:api[_-]?key|token|secret|password)=)[^&#\s]+")


@dataclass(frozen=True)
class ArchivedSourceResult:
    """Secret-safe source outcome stored in run metadata."""

    source_id: str
    status: Literal["success", "failure"]
    article_count: int
    error: str | None = None


@dataclass(frozen=True)
class DailyRun:
    """Daily Run record defined by the product specification."""

    date: str
    timezone: str
    started_at: str
    completed_at: str | None
    status: RunStatus
    source_results: list[ArchivedSourceResult]
    article_count: int
    event_count: int
    selected_event_ids: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class ArchivePaths:
    """Paths updated by one idempotent archive operation."""

    articles: Path
    run: Path
    state: Path


def reporting_date(moment: datetime) -> str:
    """Return the calendar date for an aware timestamp in Singapore."""
    if moment.tzinfo is None:
        raise ValueError("moment must be timezone-aware")
    return moment.astimezone(SINGAPORE).date().isoformat()


def redact_secrets(value: str) -> str:
    """Remove common credential forms from persisted diagnostic text."""
    redacted = _BEARER.sub("Bearer [REDACTED]", value)
    redacted = _QUERY_SECRET.sub(r"\1[REDACTED]", redacted)
    return _SECRET_FIELD.sub(r"\1\2[REDACTED]", redacted)


def sanitize_source_results(
    results: Sequence[SourceResult],
) -> list[ArchivedSourceResult]:
    """Copy ingestion results while redacting diagnostic credentials."""
    return [
        ArchivedSourceResult(
            item.source_id,
            item.status,
            item.article_count,
            redact_secrets(item.error) if item.error else None,
        )
        for item in results
    ]


def create_daily_run(
    *,
    now: datetime,
    started_at: datetime,
    status: RunStatus,
    source_results: Sequence[SourceResult] = (),
    article_count: int = 0,
    event_count: int = 0,
    selected_event_ids: Sequence[str] = (),
    warnings: Sequence[str] = (),
    completed_at: datetime | None = None,
) -> DailyRun:
    """Build a validated run whose identity is its Singapore reporting date."""
    if now.tzinfo is None or started_at.tzinfo is None:
        raise ValueError("run timestamps must be timezone-aware")
    if completed_at is not None and completed_at.tzinfo is None:
        raise ValueError("completed_at must be timezone-aware")
    return DailyRun(
        date=reporting_date(now),
        timezone="Asia/Singapore",
        started_at=started_at.isoformat(),
        completed_at=completed_at.isoformat() if completed_at else None,
        status=status,
        source_results=sanitize_source_results(source_results),
        article_count=article_count,
        event_count=event_count,
        selected_event_ids=list(selected_event_ids),
        warnings=[redact_secrets(item) for item in warnings],
    )


def atomic_write_json(
    path: Path, payload: object, *, replace: Replace = os.replace
) -> None:
    """Atomically replace a JSON file, preserving the old file on interruption."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            json.dump(payload, temporary, ensure_ascii=False, indent=2, sort_keys=True)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        replace(temporary_name, str(path))
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def archive_daily_run(
    data_dir: Path,
    articles: Sequence[Article],
    run: DailyRun,
    *,
    replace: Replace = os.replace,
) -> ArchivePaths:
    """Create or update the sole private archive for a reporting date."""
    articles_path = data_dir / "articles" / f"{run.date}.json"
    run_path = data_dir / "runs" / run.date / "run.json"
    state_path = data_dir / "state.json"
    atomic_write_json(articles_path, articles_json(list(articles)), replace=replace)
    atomic_write_json(run_path, asdict(run), replace=replace)
    atomic_write_json(
        state_path,
        {"latest_reporting_date": run.date, "latest_status": run.status},
        replace=replace,
    )
    return ArchivePaths(articles_path, run_path, state_path)
