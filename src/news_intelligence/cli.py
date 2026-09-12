"""Command-line entry point."""

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from news_intelligence.archive import reporting_date
from news_intelligence.ingestion import collect, load_sources, result_json
from news_intelligence.scheduling import AttemptResult, run_daily
from news_intelligence.wechat import messages_from_publication, send_publication


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level command parser."""
    parser = argparse.ArgumentParser(
        prog="news_intelligence",
        description="Generate and publish a daily news intelligence brief.",
    )
    subparsers = parser.add_subparsers(dest="command")
    collect_parser = subparsers.add_parser("collect", help="collect configured sources")
    collect_parser.add_argument(
        "--sources", type=Path, default=Path("config/sources.example.json")
    )
    collect_parser.add_argument(
        "--live", action="store_true", help="confirm intentional network use"
    )
    run_parser = subparsers.add_parser("run", help="apply daily scheduling policy")
    run_parser.add_argument(
        "--catch-up",
        action="store_true",
        help="run only today's Singapore report after downtime",
    )
    run_parser.add_argument("--workspace", type=Path, default=Path.cwd())
    send_parser = subparsers.add_parser("send-wechat", help="send a published brief")
    send_parser.add_argument("--brief", type=Path, required=True)
    send_parser.add_argument(
        "--state", type=Path, default=Path("data/wechat-state.json")
    )
    send_parser.add_argument(
        "--live-send", action="store_true", help="confirm intentional message sending"
    )
    return parser


def _ready_attempt(workspace: Path, reporting_date: str) -> AttemptResult:
    """Validate the brief prepared by the scheduled Codex task."""
    try:
        payload = json.loads(
            (workspace / "public/latest.json").read_text(encoding="utf-8")
        )
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return AttemptResult("failed", warning="no valid prepared publication")
    if not isinstance(payload, dict) or payload.get("date") != reporting_date:
        return AttemptResult("failed", warning="prepared publication is stale")
    value = payload.get("status")
    if value == "complete":
        return AttemptResult("complete", sufficient_evidence=True)
    if value == "partial":
        return AttemptResult("partial", sufficient_evidence=True)
    return AttemptResult("failed", warning="prepared publication has invalid status")


def run_command(workspace: Path, now: datetime) -> int:
    """Apply recovery policy to the publication prepared in this workspace."""
    resolved = workspace.resolve()
    date_key = reporting_date(now)
    result = run_daily(
        resolved,
        now,
        lambda _attempt: _ready_attempt(resolved, date_key),
        lambda _attempt: None,
    )
    print(json.dumps(result.__dict__, ensure_ascii=False, default=list))
    return 0 if result.action in {"published", "duplicate", "overlap"} else 1


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    args = build_parser().parse_args(argv)
    if args.command == "collect":
        if not args.live:
            build_parser().error(
                "collect requires --live; tests use deterministic fixtures"
            )
        print(result_json(collect(load_sources(args.sources), datetime.now(UTC))))
    elif args.command == "run":
        if not args.catch_up:
            build_parser().error("run requires --catch-up")
        return run_command(args.workspace, datetime.now(UTC))
    elif args.command == "send-wechat":
        payload = json.loads(args.brief.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            build_parser().error("brief must be a JSON object")
        if args.live_send:
            print(json.dumps({"sent": send_publication(payload, args.state)}))
        else:
            print(
                json.dumps(
                    [
                        message.__dict__
                        for message in messages_from_publication(payload)
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
            )
    return 0
