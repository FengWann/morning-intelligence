"""Deterministic static publishing checks."""

import json
import threading
from dataclasses import replace
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

import pytest

from news_intelligence.briefing import BriefInput, GeneratedBrief, build_input
from news_intelligence.publishing import (
    build_publication,
    publish,
    render_intelligence_markdown,
    scan_public_files,
    validate_public_tree,
)
from news_intelligence.synthesis import (
    ImpactLink,
    IntelligenceTheme,
    OpportunityHypothesis,
    ProblemSignal,
    ThemeEvidence,
)
from tests.test_briefing import article, ranked


def fixture_publication(tmp_path: Path) -> tuple[BriefInput, GeneratedBrief]:
    source = article("reuters", 1, "Company announces a new policy")
    data = build_input(
        "2026-09-12",
        [ranked("event-1", [source], "Business")],
        {source.id: source},
        tmp_path / "history",
    )
    brief = GeneratedBrief(
        "# 简报\n\n[REUTERS](https://reuters.test/1)\n", "今日简报", 600, ()
    )
    return data, brief


def theme(reporting_date: str = "2026-09-12") -> IntelligenceTheme:
    return IntelligenceTheme(
        "theme_1234567890abcdef",
        reporting_date,
        "监管变化开始影响企业采购",
        "新规正在把合规成本前移到采购环节。",
        ("business", "asia"),
        ("event-1",),
        (ThemeEvidence("event-1", "REUTERS", "https://reuters.test/1"),),
        "new",
        "企业首次公开调整采购流程。",
        (
            ImpactLink(
                "新规实施",
                "审核前移",
                ("企业采购团队",),
                "采购周期可能延长",
                "medium",
                ("event-1",),
            ),
        ),
        (
            ProblemSignal(
                "采购团队需要重复核验材料",
                ("企业采购团队",),
                "operational",
                ("event-1",),
            ),
        ),
        ("执行细则仍可能调整",),
        ("尚无长期数据",),
        "medium",
        80,
        "变化和证据较强，但长期影响仍不确定。",
    )


def opportunity() -> OpportunityHypothesis:
    return OpportunityHypothesis(
        "采购团队需要重复核验材料",
        ("企业采购团队",),
        "目前由人工逐项核验材料。",
        "人工流程速度慢且容易遗漏。",
        "AI 可辅助提取材料并标记缺口。",
        "可测试一个采购材料核验助手。",
        ("企业合规负责人",),
        ("event-1",),
        ("企业愿意试用辅助工具",),
        "访谈五名采购负责人并测试样例。",
        "low",
    )


def test_build_publish_and_serve_complete_site(tmp_path: Path) -> None:
    data, brief = fixture_publication(tmp_path)
    publication = build_publication(
        data,
        brief,
        status="complete",
        generated_at=datetime(2026, 9, 12, 0, 40, tzinfo=UTC),
        base_url="https://example.github.io/news/",
    )
    paths = publish(tmp_path / "public", publication, brief.markdown)
    assert len(paths) == 4
    validate_public_tree(tmp_path / "public")
    latest = json.loads((tmp_path / "public/latest.json").read_text(encoding="utf-8"))
    assert latest == {
        "brief_url": "https://example.github.io/news/briefs/2026-09-12.md",
        "date": "2026-09-12",
        "generated_at": "2026-09-12T00:40:00+00:00",
        "speech_text": "今日简报",
        "status": "complete",
    }
    payload = json.loads(
        (tmp_path / "public/briefs/2026-09-12.json").read_text(encoding="utf-8")
    )
    assert payload["events"][0]["sources"][0]["url"].startswith("https://")
    assert "2026-09-12" in (tmp_path / "public/index.html").read_text("utf-8")

    handler = lambda *args: SimpleHTTPRequestHandler(  # noqa: E731
        *args, directory=str(tmp_path / "public")
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/latest.json") as response:
            assert json.load(response)["date"] == "2026-09-12"
    finally:
        server.shutdown()
        thread.join()


def test_planted_secrets_private_paths_and_unlisted_files_are_blocked() -> None:
    unsafe = {
        "briefs/2026-09-12.md": "api_key=planted-secret",
        "latest.json": "{}",
    }
    with pytest.raises(ValueError, match="unsafe public content"):
        scan_public_files(unsafe)
    with pytest.raises(ValueError, match="allowlist"):
        scan_public_files({"data/private.json": "{}"})
    with pytest.raises(ValueError, match="unsafe public content"):
        scan_public_files({"latest.json": r"C:\\Users\\admin\\private.json"})


def test_invalid_run_preserves_previous_valid_brief(tmp_path: Path) -> None:
    public = tmp_path / "public"
    public.mkdir()
    old_latest = '{"date":"2026-09-11"}\n'
    (public / "latest.json").write_text(old_latest, encoding="utf-8")
    data, brief = fixture_publication(tmp_path)
    publication = build_publication(
        data,
        brief,
        status="partial",
        generated_at=datetime(2026, 9, 12, tzinfo=UTC),
        base_url="https://example.test",
    )
    poisoned = replace(brief, markdown="Authorization: Bearer planted-token")
    with pytest.raises(ValueError, match="unsafe public content"):
        publish(public, publication, poisoned.markdown)
    assert (public / "latest.json").read_text(encoding="utf-8") == old_latest
    assert not (public / "briefs/2026-09-12.md").exists()


@pytest.mark.parametrize(
    ("date", "url", "aware"),
    [
        ("bad", "https://example.test", True),
        ("2026-09-12", "http://x", True),
        ("2026-09-12", "https://x", False),
    ],
)
def test_publication_contract_validation(
    tmp_path: Path, date: str, url: str, aware: bool
) -> None:
    data, brief = fixture_publication(tmp_path)
    moment = datetime(2026, 9, 12, tzinfo=UTC) if aware else datetime(2026, 9, 12)
    with pytest.raises(ValueError):
        build_publication(
            replace(data, reporting_date=date),
            brief,
            status="complete",
            generated_at=moment,
            base_url=url,
        )


def test_tree_validation_detects_planted_private_file(tmp_path: Path) -> None:
    public = tmp_path / "public"
    public.mkdir()
    (public / "private.log").write_text("internal log", encoding="utf-8")
    with pytest.raises(ValueError, match="allowlist"):
        validate_public_tree(public)


def test_full_article_body_is_blocked() -> None:
    body = "Publisher-owned sentence " * 20
    with pytest.raises(ValueError, match="full article body"):
        scan_public_files({"briefs/2026-09-12.md": body}, private_article_bodies=[body])


def test_structured_analysis_is_validated_rendered_and_published(
    tmp_path: Path,
) -> None:
    data, brief = fixture_publication(tmp_path)
    publication = build_publication(
        data,
        brief,
        status="complete",
        generated_at=datetime(2026, 9, 12, tzinfo=UTC),
        base_url="https://example.test",
        intelligence_themes=(theme(),),
        opportunity_hypothesis=opportunity(),
    )
    markdown = render_intelligence_markdown(publication)
    assert "核心判断" in markdown and "不确定性与反证" in markdown
    assert "采购材料核验助手" in markdown
    publish(tmp_path / "public", publication, "legacy")
    payload = json.loads(
        (tmp_path / "public/briefs/2026-09-12.json").read_text(encoding="utf-8")
    )
    assert payload["intelligence_themes"][0]["event_ids"] == ["event-1"]
    assert "intelligence_themes" not in json.loads(
        (tmp_path / "public/latest.json").read_text(encoding="utf-8")
    )
    assert "legacy" not in (tmp_path / "public/briefs/2026-09-12.md").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    "bad_theme",
    [
        replace(theme(), reporting_date="2026-09-11"),
        replace(theme(), event_ids=("unknown",)),
        replace(
            theme(),
            evidence=(ThemeEvidence("event-1", "R", "file:///private"),),
        ),
    ],
)
def test_structured_publication_rejects_invalid_themes(
    tmp_path: Path, bad_theme: IntelligenceTheme
) -> None:
    data, brief = fixture_publication(tmp_path)
    with pytest.raises(ValueError):
        build_publication(
            data,
            brief,
            status="complete",
            generated_at=datetime(2026, 9, 12, tzinfo=UTC),
            base_url="https://example.test",
            intelligence_themes=(bad_theme,),
        )


def test_rejects_ungrounded_opportunity_and_nested_private_fields(
    tmp_path: Path,
) -> None:
    data, brief = fixture_publication(tmp_path)
    with pytest.raises(ValueError, match="grounded"):
        build_publication(
            data,
            brief,
            status="complete",
            generated_at=datetime(2026, 9, 12, tzinfo=UTC),
            base_url="https://example.test",
            intelligence_themes=(theme(),),
            opportunity_hypothesis=replace(opportunity(), problem_zh="另一个问题"),
        )
    with pytest.raises(ValueError, match="unsafe public content"):
        scan_public_files({"briefs/2026-09-12.json": '{"theme":{"raw_text":"secret"}}'})


def test_publish_revalidates_direct_publication_before_writing(tmp_path: Path) -> None:
    data, brief = fixture_publication(tmp_path)
    publication = build_publication(
        data,
        brief,
        status="complete",
        generated_at=datetime(2026, 9, 12, tzinfo=UTC),
        base_url="https://example.test",
    )
    invalid = replace(publication, intelligence_themes=(theme("2026-09-11"),))
    with pytest.raises(ValueError, match="reporting_date"):
        publish(tmp_path / "public", invalid, brief.markdown)
    assert not (tmp_path / "public").exists()
