"""Automated iPhone Shortcut contract simulation."""

import json
from datetime import date

import pytest

from news_intelligence.shortcut import UNAVAILABLE_MESSAGE, evaluate_latest

TODAY = date(2026, 9, 12)


@pytest.mark.parametrize("status", ["complete", "partial"])
def test_current_complete_or_partial_brief_is_spoken(status: str) -> None:
    response = json.dumps(
        {"date": "2026-09-12", "status": status, "speech_text": " 今日简报 "}
    )
    assert evaluate_latest(response, TODAY).action == "speak_brief"
    assert evaluate_latest(response, TODAY).text == "今日简报"


def test_stale_brief_is_never_spoken_as_current() -> None:
    response = json.dumps(
        {"date": "2026-09-11", "status": "complete", "speech_text": "旧简报"}
    )
    assert evaluate_latest(response, TODAY).text == UNAVAILABLE_MESSAGE


def test_offline_request_announces_unavailable() -> None:
    assert evaluate_latest(None, TODAY).text == UNAVAILABLE_MESSAGE


@pytest.mark.parametrize(
    "response",
    [
        "not json",
        "[]",
        b"\xff",
        json.dumps({"date": "2026-09-12", "status": "failed", "speech_text": "x"}),
        json.dumps({"date": "2026-09-12", "status": "complete"}),
        json.dumps({"date": "2026-09-12", "status": "complete", "speech_text": " "}),
    ],
)
def test_malformed_or_unacceptable_response_is_not_spoken(
    response: str | bytes,
) -> None:
    decision = evaluate_latest(response, TODAY)
    assert decision.action == "announce_unavailable"
    assert decision.text == UNAVAILABLE_MESSAGE
