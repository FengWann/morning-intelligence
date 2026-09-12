"""Deliver a published brief to personal WeChat through ServerChan."""

from __future__ import annotations

import json
import os
import re
import tempfile
import urllib as urllib
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from news_intelligence.synthesis import (
    IntelligenceTheme,
    parse_proposed_theme,
    select_themes,
    validate_theme,
)

SERVERCHAN_URL = "https://sctapi.ftqq.com/{sendkey}.send"
_SECTIONS = (
    ("政治与全球", "政治与全球事务。"),
    ("商业", "商业。"),
    ("人工智能与科技", "人工智能与科技。"),
    ("新加坡与亚洲", "新加坡与亚洲。"),
)
_FINAL_HEADINGS = ("发生了什么变化。", "机会雷达。")


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
    """Create structured theme messages, falling back only for legacy payloads."""
    date = payload.get("date")
    if not isinstance(date, str) or not date:
        raise ValueError("publication must contain a date")
    if "intelligence_themes" in payload:
        return _structured_messages(date, payload)
    speech = payload.get("speech_text")
    if not isinstance(speech, str):
        speech = ""
    headings = (
        tuple(heading for _, heading in _SECTIONS) + _FINAL_HEADINGS + ("值得关注。",)
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
    result.append(Message(f"{date} · 变化与机会雷达", _compact(final)))

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
        Message(item.title, item.body or fallback or "今天没有相关内容。")
        for item in result
    )


def _structured_messages(date: str, payload: Mapping[str, Any]) -> tuple[Message, ...]:
    raw_themes = payload.get("intelligence_themes")
    if not isinstance(raw_themes, list):
        raise ValueError("intelligence_themes must be a list")
    event_ids = _published_event_ids(payload.get("events"))
    themes = tuple(_theme_mapping(item) for item in raw_themes)
    for theme in themes:
        validate_theme(theme, event_ids)
        if theme.reporting_date != date:
            raise ValueError("theme reporting_date must match publication date")
    selected = select_themes(themes)
    result = [
        Message(f"{date} · {theme.title_zh}", _compact(_theme_body(theme)))
        for theme in selected
    ]
    summary = _summary_body(selected, payload.get("opportunity_hypothesis"))
    if summary:
        result.append(Message(f"{date} · 变化与机会雷达", _compact(summary)))
    return tuple(result[:5])


def _published_event_ids(value: object) -> set[str]:
    if not isinstance(value, list):
        raise ValueError("structured publication must contain events")
    result = {
        item["id"]
        for item in value
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    if len(result) != len(value):
        raise ValueError("publication events are invalid")
    return result


def _theme_mapping(value: object) -> IntelligenceTheme:
    if not isinstance(value, Mapping):
        raise ValueError("intelligence theme must be an object")
    try:
        return parse_proposed_theme(value)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid intelligence theme") from exc


def _theme_body(theme: IntelligenceTheme) -> str:
    evidence = "\n".join(
        f"- [{item.source_name}]({item.url})" for item in theme.evidence
    )
    impacts = "\n".join(
        f"- {item.cause_zh} → {item.mechanism_zh} → {item.effect_zh}"
        for item in theme.impact_chain
    )
    uncertainty = (
        "；".join((*theme.counter_evidence_zh, *theme.uncertainties_zh))
        or "暂无显著反证，仍需持续验证。"
    )
    return (
        f"核心判断：{theme.thesis_zh}\n\n"
        f"支撑事件与来源：\n{evidence}\n\n"
        f"变化：{theme.change_summary_zh}\n\n"
        f"影响链：\n{impacts}\n\n"
        f"不确定性与反证：{uncertainty}"
    )


def _summary_body(themes: Sequence[IntelligenceTheme], opportunity: object) -> str:
    parts: list[str] = []
    if themes:
        parts.append(
            "变化总结：\n"
            + "\n".join(
                f"- {item.title_zh}：{item.change_summary_zh}" for item in themes
            )
        )
    if isinstance(opportunity, Mapping):
        problem = opportunity.get("problem_zh")
        product = opportunity.get("potential_product_zh")
        next_step = opportunity.get("next_validation_step_zh")
        if all(
            isinstance(item, str) and item.strip()
            for item in (problem, product, next_step)
        ):
            parts.append(
                f"机会雷达：{problem}\n产品假设：{product}\n下一步：{next_step}"
            )
    elif themes:
        parts.append("机会雷达：当前问题证据不足，今天不提出机会假设。")
    elif not parts:
        parts.append("当前证据不足，今天不推送未经验证的情报主题。")
    return "\n\n".join(parts)


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
