"""Deterministic model of the public iPhone Shortcut contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Literal

DeliveryAction = Literal["speak_brief", "announce_unavailable"]
ALLOWED_STATUSES = frozenset({"complete", "partial"})
UNAVAILABLE_MESSAGE = "今天的简报尚未准备好，请稍后再试。"


@dataclass(frozen=True)
class DeliveryDecision:
    """The only two actions the Shortcut is allowed to take."""

    action: DeliveryAction
    text: str


def evaluate_latest(response: str | bytes | None, today: date) -> DeliveryDecision:
    """Validate ``latest.json`` and refuse stale or malformed content."""
    if response is None:
        return DeliveryDecision("announce_unavailable", UNAVAILABLE_MESSAGE)
    try:
        value = json.loads(response)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return DeliveryDecision("announce_unavailable", UNAVAILABLE_MESSAGE)
    if not isinstance(value, dict):
        return DeliveryDecision("announce_unavailable", UNAVAILABLE_MESSAGE)
    reporting_date = value.get("date")
    status = value.get("status")
    speech_text = value.get("speech_text")
    if (
        reporting_date != today.isoformat()
        or status not in ALLOWED_STATUSES
        or not isinstance(speech_text, str)
        or not speech_text.strip()
    ):
        return DeliveryDecision("announce_unavailable", UNAVAILABLE_MESSAGE)
    return DeliveryDecision("speak_brief", speech_text.strip())
