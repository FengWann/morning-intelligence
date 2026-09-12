"""Controlled-clock scheduling and recovery scenarios."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from news_intelligence import cli
from news_intelligence.scheduling import (
    AttemptResult,
    ScheduleResult,
    retry_source,
    run_daily,
)

SG = ZoneInfo("Asia/Singapore")
PROJECT = Path(__file__).parents[1]


def at(day: int, hour: int = 8, minute: int = 0) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=SG)


def status(workspace: Path, day: str) -> str:
    path = workspace / "data" / "runs" / day / "run.json"
    return str(json.loads(path.read_text(encoding="utf-8"))["status"])


def execute(
    workspace: Path,
    now: datetime,
    outcomes: list[AttemptResult],
    publications: list[AttemptResult],
) -> ScheduleResult:
    return run_daily(
        workspace,
        now,
        lambda attempt: outcomes[attempt - 1],
        publications.append,
    )


def test_complete_and_same_day_rerun_are_idempotent(tmp_path: Path) -> None:
    publications: list[AttemptResult] = []
    first = execute(tmp_path, at(12), [AttemptResult("complete")], publications)
    second = execute(tmp_path, at(12, 8, 30), [], publications)
    assert first.action == "published" and first.attempts == 1
    assert second.action == "duplicate" and second.attempts == 0
    assert publications == [AttemptResult("complete")]


def test_activation_definition_targets_this_project() -> None:
    instructions = (PROJECT / "docs/codex-automation.md").read_text(encoding="utf-8")
    assert "every day at 08:00" in instructions
    assert "timezone `Asia/Singapore`" in instructions
    assert str(PROJECT) in instructions
    assert "python -m news_intelligence run --catch-up" in instructions


def test_partial_requires_sufficient_verified_evidence(tmp_path: Path) -> None:
    publications: list[AttemptResult] = []
    accepted = execute(
        tmp_path,
        at(12),
        [AttemptResult("partial", sufficient_evidence=True)],
        publications,
    )
    assert (
        accepted.action == "published" and status(tmp_path, "2026-09-12") == "partial"
    )

    other = tmp_path / "other"
    rejected = execute(
        other,
        at(12, 8, 50),
        [AttemptResult("partial", sufficient_evidence=False)],
        [],
    )
    assert rejected.action == "failed" and status(other, "2026-09-12") == "failed"


def test_failed_full_run_retries_once_before_cutoff(tmp_path: Path) -> None:
    published: list[AttemptResult] = []
    result = execute(
        tmp_path,
        at(12, 8, 30),
        [AttemptResult("failed"), AttemptResult("complete")],
        published,
    )
    assert result.action == "published" and result.attempts == 2
    assert len(published) == 1

    late = execute(tmp_path / "late", at(12, 8, 45), [AttemptResult("failed")], [])
    assert late.action == "failed" and late.attempts == 1


def test_multi_day_recovery_marks_old_days_and_only_runs_today(tmp_path: Path) -> None:
    old = tmp_path / "data/runs/2026-09-08/run.json"
    old.parent.mkdir(parents=True)
    old.write_text('{"status":"complete"}', encoding="utf-8")
    calls: list[int] = []

    def run_once(attempt: int) -> AttemptResult:
        calls.append(attempt)
        return AttemptResult("complete")

    result = run_daily(
        tmp_path,
        at(12, 10),
        run_once,
        lambda _result: None,
    )
    assert result.missed_dates == ("2026-09-09", "2026-09-10", "2026-09-11")
    assert calls == [1]
    assert all(
        status(tmp_path, f"2026-09-{day:02}") == "missed" for day in range(9, 12)
    )


def test_overlap_and_failed_run_preserve_public_brief(tmp_path: Path) -> None:
    public = tmp_path / "public"
    public.mkdir()
    latest = public / "latest.json"
    latest.write_text('{"date":"2026-09-11"}\n', encoding="utf-8")
    lock = tmp_path / "data/locks/2026-09-12.lock"
    lock.parent.mkdir(parents=True)
    lock.touch()
    overlap = execute(tmp_path, at(12), [AttemptResult("complete")], [])
    assert overlap.action == "overlap"
    lock.unlink()
    failed = execute(tmp_path, at(12, 8, 50), [AttemptResult("failed")], [])
    assert failed.action == "failed"
    assert latest.read_text(encoding="utf-8") == '{"date":"2026-09-11"}\n'


def test_source_retry_is_bounded_and_uses_backoff() -> None:
    calls = 0
    waits: list[float] = []

    def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise OSError("offline")
        return "ok"

    assert retry_source(flaky, wait=waits.append) == "ok"
    assert calls == 3 and waits == [1.0, 2.0]

    def always_fails() -> str:
        raise OSError("offline")

    with pytest.raises(OSError, match="offline"):
        retry_source(
            always_fails, attempts=2, backoff_seconds=(0,), wait=lambda _: None
        )
    with pytest.raises(ValueError, match="bounded"):
        retry_source(always_fails, attempts=0)


def test_invalid_clock_and_corrupt_records_are_safe(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        run_daily(
            tmp_path,
            datetime(2026, 9, 12),
            lambda _: AttemptResult("complete"),
            lambda _: None,
        )
    corrupt = tmp_path / "data/runs/not-a-date/run.json"
    corrupt.parent.mkdir(parents=True)
    corrupt.write_text("bad", encoding="utf-8")
    today = tmp_path / "data/runs/2026-09-12/run.json"
    today.parent.mkdir(parents=True)
    today.write_text("bad", encoding="utf-8")
    result = run_daily(
        tmp_path, at(12), lambda _: AttemptResult("complete"), lambda _: None
    )
    assert result.action == "published"


def test_lock_is_released_when_pipeline_raises(tmp_path: Path) -> None:
    def explode(_attempt: int) -> AttemptResult:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        run_daily(tmp_path, at(12), explode, lambda _: None)
    assert not (tmp_path / "data/locks/2026-09-12.lock").exists()


@pytest.mark.parametrize("publication_status", ["complete", "partial"])
def test_run_cli_accepts_prepared_current_publication(
    tmp_path: Path, publication_status: str, capsys: pytest.CaptureFixture[str]
) -> None:
    public = tmp_path / "public"
    public.mkdir()
    (public / "latest.json").write_text(
        json.dumps({"date": "2026-09-12", "status": publication_status}),
        encoding="utf-8",
    )
    assert cli.run_command(tmp_path, at(12)) == 0
    assert json.loads(capsys.readouterr().out)["action"] == "published"


def test_run_cli_fails_closed_for_missing_stale_or_invalid_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.run_command(tmp_path, at(12, 8, 50)) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"

    for name, payload in (
        ("stale", {"date": "2026-09-11", "status": "complete"}),
        ("invalid", {"date": "2026-09-12", "status": "failed"}),
    ):
        workspace = tmp_path / name
        public = workspace / "public"
        public.mkdir(parents=True)
        (public / "latest.json").write_text(json.dumps(payload), encoding="utf-8")
        assert cli.run_command(workspace, at(12, 8, 50)) == 1
        capsys.readouterr()


def test_main_exposes_required_catch_up_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list[Path] = []

    def fake_run(workspace: Path, _now: datetime) -> int:
        called.append(workspace)
        return 0

    monkeypatch.setattr(cli, "run_command", fake_run)
    assert cli.main(["run", "--catch-up", "--workspace", str(tmp_path)]) == 0
    assert called == [tmp_path]
    with pytest.raises(SystemExit):
        cli.main(["run", "--workspace", str(tmp_path)])
