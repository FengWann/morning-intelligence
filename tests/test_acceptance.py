"""Seven-day acceptance of the integrated pipeline."""

import json
from datetime import date
from pathlib import Path

import pytest

from news_intelligence.acceptance import run_seven_day_acceptance


def test_seven_day_acceptance_uses_real_pipeline_and_records_evidence(
    tmp_path: Path,
) -> None:
    report = run_seven_day_acceptance(tmp_path.resolve(), date(2026, 9, 1))

    assert report.passed
    assert report.on_time_days == 6
    assert len(report.days) == 7
    assert all(600 <= item.estimated_seconds <= 900 for item in report.days)
    assert all(item.evidence_urls for item in report.days)
    assert all(set(item.category_counts.values()) == {1} for item in report.days)
    assert all(max(item.source_counts.values()) == 2 for item in report.days)
    assert all(
        set(item.editorial_labels.values()) == {"Useful"} for item in report.days
    )
    assert all(item.missed_events == () for item in report.days)
    assert report.days[3].shortcut_action_at_0900 == "announce_unavailable"
    assert all(
        item.shortcut_action_at_0900 == "speak_brief"
        for index, item in enumerate(report.days)
        if index != 3
    )

    assert len(list((tmp_path / "data/runs").glob("*/run.json"))) == 7
    assert len(list((tmp_path / "data/events").glob("*.json"))) == 7
    assert len(list((tmp_path / "public/briefs").glob("*.md"))) == 7
    latest = json.loads((tmp_path / "public/latest.json").read_text(encoding="utf-8"))
    assert latest["date"] == "2026-09-07"
    persisted = json.loads(
        (tmp_path / "data/acceptance/report.json").read_text(encoding="utf-8")
    )
    assert persisted["passed"] is True
    assert len(persisted["days"]) == 7


def test_acceptance_requires_isolated_absolute_workspace(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="absolute"):
        run_seven_day_acceptance(Path("relative"), date(2026, 9, 1))
