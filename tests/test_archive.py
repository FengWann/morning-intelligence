"""Tests for private daily archive and state persistence."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

import pytest

from news_intelligence.archive import (
    DailyRun,
    archive_daily_run,
    atomic_write_json,
    create_daily_run,
    redact_secrets,
    reporting_date,
)
from news_intelligence.ingestion import CollectedArticle, SourceResult
from news_intelligence.normalization import normalize_and_deduplicate


def article() -> CollectedArticle:
    return CollectedArticle(
        "bbc",
        "BBC",
        "Important event",
        "https://example.test/story",
        "2026-09-11T23:30:00+00:00",
        "Evidence summary",
        "en",
        "2026-09-12T00:01:00+00:00",
    )


def run(status: str = "complete") -> DailyRun:
    assert status in {"running", "complete", "partial", "failed", "missed"}
    return create_daily_run(
        now=datetime(2026, 9, 11, 16, 30, tzinfo=UTC),
        started_at=datetime(2026, 9, 11, 16, tzinfo=UTC),
        completed_at=datetime(2026, 9, 11, 16, 20, tzinfo=UTC),
        status=status,  # type: ignore[arg-type]
        source_results=[
            SourceResult("bbc", "failure", 0, "token=abc123 URL?api_key=xyz")
        ],
        article_count=1,
        warnings=["Authorization: Bearer very.secret.token"],
    )


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_reporting_date_uses_singapore_and_rejects_naive_time() -> None:
    assert reporting_date(datetime(2026, 9, 11, 16, tzinfo=UTC)) == "2026-09-12"
    with pytest.raises(ValueError, match="timezone-aware"):
        reporting_date(datetime(2026, 9, 12))


def test_create_run_validates_timestamps_and_supports_missed() -> None:
    missed = create_daily_run(
        now=datetime(2026, 9, 12, tzinfo=UTC),
        started_at=datetime(2026, 9, 12, tzinfo=UTC),
        status="missed",
    )
    assert missed.status == "missed"
    assert missed.completed_at is None
    with pytest.raises(ValueError, match="timestamps"):
        create_daily_run(
            now=datetime(2026, 9, 12),
            started_at=datetime(2026, 9, 12, tzinfo=UTC),
            status="running",
        )
    with pytest.raises(ValueError, match="completed_at"):
        create_daily_run(
            now=datetime(2026, 9, 12, tzinfo=UTC),
            started_at=datetime(2026, 9, 12, tzinfo=UTC),
            completed_at=datetime(2026, 9, 12),
            status="complete",
        )


def test_archive_is_private_secret_safe_and_same_day_idempotent(
    tmp_path: Path,
) -> None:
    articles = normalize_and_deduplicate([article()])
    paths = archive_daily_run(tmp_path / "data", articles, run())
    first_names = sorted(
        path.relative_to(tmp_path) for path in tmp_path.rglob("*.json")
    )
    updated = run("partial")
    paths_again = archive_daily_run(tmp_path / "data", articles, updated)
    second_names = sorted(
        path.relative_to(tmp_path) for path in tmp_path.rglob("*.json")
    )

    assert paths == paths_again
    assert first_names == second_names
    assert read_json(paths.articles) == [
        {
            "canonical_url": "https://example.test/story",
            "collected_at": "2026-09-12T00:01:00+00:00",
            "content_hash": articles[0].content_hash,
            "country": None,
            "feed_summary": "Evidence summary",
            "id": articles[0].id,
            "language": "en",
            "published_at": "2026-09-11T23:30:00+00:00",
            "rejection_reason": None,
            "source_id": "bbc",
            "source_name": "BBC",
            "status": "accepted",
            "text": None,
            "title": "Important event",
            "topics": [],
            "url": "https://example.test/story",
        }
    ]
    run_payload = read_json(paths.run)
    assert isinstance(run_payload, dict)
    serialized = json.dumps(run_payload)
    assert "abc123" not in serialized and "xyz" not in serialized
    assert "very.secret.token" not in serialized
    assert run_payload["status"] == "partial"
    assert read_json(paths.state) == {
        "latest_reporting_date": "2026-09-12",
        "latest_status": "partial",
    }


def test_interrupted_atomic_write_preserves_valid_file(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    atomic_write_json(target, {"version": 1})

    def interrupt(_source: str, _destination: str) -> NoReturn:
        raise OSError("simulated interruption")

    with pytest.raises(OSError, match="simulated"):
        atomic_write_json(target, {"version": 2}, replace=interrupt)
    assert read_json(target) == {"version": 1}
    assert list(tmp_path.glob("*.tmp")) == []


def test_redaction_forms_and_success_result(tmp_path: Path) -> None:
    text = "password = hunter2, secret:foo Bearer ABC.def? api-key=last"
    assert "hunter2" not in redact_secrets(text)
    assert "foo" not in redact_secrets(text)
    assert "ABC.def" not in redact_secrets(text)
    success = create_daily_run(
        now=datetime(2026, 9, 12, tzinfo=UTC),
        started_at=datetime(2026, 9, 12, tzinfo=UTC),
        status="running",
        source_results=[SourceResult("bbc", "success", 2)],
    )
    paths = archive_daily_run(tmp_path, [], success, replace=os.replace)
    assert read_json(paths.run) != {}
