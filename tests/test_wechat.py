"""Tests for personal WeChat delivery."""

import json
import urllib.parse
from pathlib import Path

import pytest

from news_intelligence import wechat
from news_intelligence.cli import main
from news_intelligence.wechat import (
    _serverchan_url,
    messages_from_publication,
    send_publication,
)


def publication() -> dict[str, object]:
    headings = (
        "政治与全球事务。",
        "商业。",
        "人工智能与科技。",
        "新加坡与亚洲。",
        "发生了什么变化。",
        "机会雷达。",
        "值得关注。",
    )
    return {
        "date": "2026-09-12",
        "speech_text": "\n\n".join(
            f"{heading}\n内容 {index}。" for index, heading in enumerate(headings)
        ),
        "events": [{"title": "Fallback", "summary": "Event summary"}],
    }


def test_builds_five_named_messages() -> None:
    messages = messages_from_publication(publication())
    assert len(messages) == 5
    assert [message.title.split(" · ")[1] for message in messages] == [
        "政治与全球",
        "商业",
        "人工智能与科技",
        "新加坡与亚洲",
        "变化与机会雷达",
    ]
    assert "发生了什么变化。" in messages[-1].body
    assert "机会雷达。" in messages[-1].body


def test_event_fallback_and_validation() -> None:
    payload = publication()
    payload["speech_text"] = None
    assert all(
        "Fallback: Event summary" in item.body
        for item in messages_from_publication(payload)
    )
    with pytest.raises(ValueError, match="date"):
        messages_from_publication({})


def test_send_is_resumable_and_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SERVERCHAN_SENDKEY", "secret-value")
    calls: list[tuple[str, bytes]] = []
    state = tmp_path / "state.json"

    def post(url: str, data: bytes) -> None:
        calls.append((url, data))
        if len(calls) == 3:
            raise RuntimeError("offline")

    with pytest.raises(RuntimeError, match="offline"):
        send_publication(publication(), state, post=post)
    assert json.loads(state.read_text())["sent"] == 2

    resumed: list[tuple[str, bytes]] = []
    assert (
        send_publication(
            publication(), state, post=lambda url, data: resumed.append((url, data))
        )
        == 3
    )
    assert (
        send_publication(
            publication(), state, post=lambda url, data: resumed.append((url, data))
        )
        == 0
    )
    assert len(resumed) == 3
    assert all("secret-value" in url for url, _ in resumed)
    assert urllib.parse.parse_qs(resumed[0][1].decode())["title"]
    assert "secret-value" not in state.read_text()


def test_send_requires_environment_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SERVERCHAN_SENDKEY", raising=False)
    with pytest.raises(RuntimeError, match="required"):
        send_publication(
            publication(), tmp_path / "state", post=lambda _url, _data: None
        )


def test_sctp_url_and_invalid_key() -> None:
    assert _serverchan_url("sctp123t-example") == (
        "https://123.push.ft07.com/send/sctp123t-example.send"
    )
    with pytest.raises(RuntimeError, match="invalid format"):
        _serverchan_url("sctp-invalid")


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_default_transport_accepts_success_and_sanitizes_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        wechat.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse({"code": 0}),
    )
    wechat._post("https://example.test/secret", b"title=x")

    monkeypatch.setattr(
        wechat.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse({"code": 1}),
    )
    with pytest.raises(RuntimeError, match="rejected"):
        wechat._post("https://example.test/secret", b"title=x")

    def offline(*_args: object, **_kwargs: object) -> FakeResponse:
        raise OSError("https://example.test/secret")

    monkeypatch.setattr(wechat.urllib.request, "urlopen", offline)
    with pytest.raises(RuntimeError, match="request failed") as error:
        wechat._post("https://example.test/secret", b"title=x")
    assert "secret" not in str(error.value)


def test_cli_dry_run_never_sends(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps(publication()), encoding="utf-8")
    assert main(["send-wechat", "--brief", str(brief)]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 5
