"""Deterministic daily scheduling and recovery policy."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Literal, TypeVar

from news_intelligence.archive import SINGAPORE, atomic_write_json

AttemptStatus = Literal["complete", "partial", "failed"]
Action = Literal["published", "failed", "duplicate", "overlap"]
T = TypeVar("T")


@dataclass(frozen=True)
class AttemptResult:
    """Result produced by one full pipeline attempt before publication."""

    status: AttemptStatus
    sufficient_evidence: bool = False
    warning: str | None = None


@dataclass(frozen=True)
class ScheduleResult:
    """Observable decision made by the scheduling policy."""

    date: str
    action: Action
    attempts: int
    status: AttemptStatus | None
    missed_dates: tuple[str, ...] = ()


def retry_source(  # noqa: UP047 - current mypy cannot parse PEP 695 syntax
    operation: Callable[[], T],
    *,
    attempts: int = 3,
    wait: Callable[[float], None] = lambda _seconds: None,
    backoff_seconds: tuple[float, ...] = (1.0, 2.0),
) -> T:
    """Retry a source operation a bounded number of times."""
    if attempts < 1 or len(backoff_seconds) < attempts - 1:
        raise ValueError("attempts and backoff_seconds do not define a bounded retry")
    for index in range(attempts):
        try:
            return operation()
        except Exception:
            if index == attempts - 1:
                raise
            wait(backoff_seconds[index])
    raise AssertionError("unreachable")


def _read_status(path: Path) -> str | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    status = value.get("status") if isinstance(value, dict) else None
    return status if isinstance(status, str) else None


def _dates_between(previous: date | None, current: date) -> tuple[date, ...]:
    if previous is None or previous >= current - timedelta(days=1):
        return ()
    return tuple(
        previous + timedelta(days=offset)
        for offset in range(1, (current - previous).days)
    )


def _latest_recorded_date(data_dir: Path) -> date | None:
    runs = data_dir / "runs"
    values: list[date] = []
    if runs.exists():
        for path in runs.iterdir():
            try:
                values.append(date.fromisoformat(path.name))
            except ValueError:
                continue
    return max(values, default=None)


def _record_status(data_dir: Path, day: date, status: str) -> None:
    atomic_write_json(
        data_dir / "runs" / day.isoformat() / "run.json",
        {"date": day.isoformat(), "timezone": "Asia/Singapore", "status": status},
    )


def run_daily(
    workspace: Path,
    now: datetime,
    run_once: Callable[[int], AttemptResult],
    publish: Callable[[AttemptResult], None],
) -> ScheduleResult:
    """Run today's pipeline once, applying catch-up, retry, and publish policy."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local_now = now.astimezone(SINGAPORE)
    today = local_now.date()
    today_text = today.isoformat()
    data_dir = workspace / "data"
    run_path = data_dir / "runs" / today_text / "run.json"
    if _read_status(run_path) in {"complete", "partial"}:
        return ScheduleResult(today_text, "duplicate", 0, None)

    lock = data_dir / "locks" / f"{today_text}.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return ScheduleResult(today_text, "overlap", 0, None)
    os.close(descriptor)

    missed = _dates_between(_latest_recorded_date(data_dir), today)
    try:
        for absent in missed:
            _record_status(data_dir, absent, "missed")

        result = run_once(1)
        attempts = 1
        cutoff = datetime.combine(today, time(8, 45), tzinfo=SINGAPORE)
        if result.status == "failed" and local_now < cutoff:
            result = run_once(2)
            attempts = 2

        publishable = result.status == "complete" or (
            result.status == "partial" and result.sufficient_evidence
        )
        final_status: AttemptStatus = result.status if publishable else "failed"
        if publishable:
            publish(result)
        _record_status(data_dir, today, final_status)
        return ScheduleResult(
            today_text,
            "published" if publishable else "failed",
            attempts,
            final_status,
            tuple(item.isoformat() for item in missed),
        )
    finally:
        lock.unlink(missing_ok=True)
