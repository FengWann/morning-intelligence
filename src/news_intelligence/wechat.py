"""Deliver a published brief to personal WeChat through ServerChan."""

from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SERVERCHAN_URL = "https://sctapi.ftqq.com/{sendkey}.send"
_SECTIONS = (
    ("Politics / Global", "Politics and global affairs."),
    ("Business", "Business."),
    ("AI / Technology", "AI and technology."),
    ("Singapore / Asia", "Singapore and Asia."),
)
_FINAL_HEADINGS = ("What changed.", "Opportunity radar.")


@dataclass(frozen=True)
class Message:
    title: str
    body: str


Post = Callable[[str, bytes], None]


def _serverchan_url(sendkey: str) -> str:
    if not sendkey.startswith("sctp"):
        return SERVERCHAN_URL.format(sendkey=sendkey)
    match = re.match(r"sctp(\d+)t", sendkey)
    if match is None:
        raise RuntimeError("SERVERCHAN_SENDKEY has an invalid format")
    return f"https://{match.group(1)}.push.ft07.com/send/{sendkey}.send"


def _section(text: str, heading: str, headings: Sequence[str]) -> str:
    start = text.find(heading)
    if start < 0:
        return ""
    start += len(heading)
    ends = [text.find(item, start) for item in headings]
    valid = [position for position in ends if position >= 0]
    return text[start : min(valid, default=len(text))].strip()


def _compact(text: str, limit: int = 2800) -> str:
    paragraphs = [" ".join(item.split()) for item in text.split("\n\n") if item.strip()]
    value = "\n\n".join(paragraphs)
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def messages_from_publication(payload: Mapping[str, Any]) -> tuple[Message, ...]:
    """Create the five fixed daily channels from a published brief payload."""
    date = payload.get("date")
    if not isinstance(date, str) or not date:
        raise ValueError("publication must contain a date")
    speech = payload.get("speech_text")
    if not isinstance(speech, str):
        speech = ""
    headings = (
        tuple(heading for _, heading in _SECTIONS)
        + _FINAL_HEADINGS
        + ("Things to watch.",)
    )
    result = [
        Message(f"{date} · {title}", _compact(_section(speech, heading, headings)))
        for title, heading in _SECTIONS
    ]
    final = "\n\n".join(
        f"{heading}\n{_section(speech, heading, headings)}"
        for heading in _FINAL_HEADINGS
        if _section(speech, heading, headings)
    )
    result.append(
        Message(f"{date} · What Changed + Opportunity Radar", _compact(final))
    )

    events = payload.get("events")
    fallback = (
        _compact(
            "\n".join(
                f"- {item.get('title', '')}: {item.get('summary', '')}"
                for item in events
                if isinstance(item, dict)
            )
        )
        if isinstance(events, list)
        else ""
    )
    return tuple(
        Message(item.title, item.body or fallback or "No items today.")
        for item in result
    )


def _post(url: str, data: bytes) -> None:
    request = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read())
    except Exception:
        # Suppress the original error because urllib may include the key-bearing URL.
        raise RuntimeError("ServerChan request failed") from None
    if not isinstance(payload, dict) or payload.get("code") != 0:
        raise RuntimeError("ServerChan rejected the message")


def _progress(path: Path, date: str) -> int:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return 0
    return int(payload.get("sent", 0)) if payload.get("date") == date else 0


def _save_progress(path: Path, date: str, sent: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary = stream.name
            json.dump({"date": date, "sent": sent}, stream)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def send_publication(
    payload: Mapping[str, Any], state_path: Path, *, post: Post = _post
) -> int:
    """Send unsent messages and return their count."""
    sendkey = os.environ.get("SERVERCHAN_SENDKEY")
    if not sendkey:
        raise RuntimeError("SERVERCHAN_SENDKEY is required for live sending")
    date = payload.get("date")
    if not isinstance(date, str):
        raise ValueError("publication must contain a date")
    messages = messages_from_publication(payload)
    sent = min(_progress(state_path, date), len(messages))
    for index, message in enumerate(messages[sent:], start=sent + 1):
        data = urllib.parse.urlencode(
            {"title": message.title, "desp": message.body}
        ).encode()
        post(_serverchan_url(sendkey), data)
        _save_progress(state_path, date, index)
    return len(messages) - sent
