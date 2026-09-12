"""Foundation smoke checks."""

from pathlib import Path
from runpy import run_module

import pytest

from news_intelligence.cli import main
from news_intelligence.config import load_settings


def test_help_runs_without_credentials(capsys: pytest.CaptureFixture[str]) -> None:
    """The CLI help path is harmless and usable after installation."""
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    else:
        raise AssertionError("argparse help should exit")

    assert "daily news intelligence brief" in capsys.readouterr().out


def test_cli_default_command_is_harmless() -> None:
    """The empty command succeeds without touching external systems."""
    assert main([]) == 0


def test_module_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    """The module entry point delegates to the CLI."""
    monkeypatch.setattr("sys.argv", ["news_intelligence"])
    with pytest.raises(SystemExit, match="0"):
        run_module("news_intelligence", run_name="__main__")


def test_settings_have_project_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Private and public paths have central, environment-free defaults."""
    for name in (
        "NEWS_INTELLIGENCE_PROJECT_ROOT",
        "NEWS_INTELLIGENCE_DATA_DIR",
        "NEWS_INTELLIGENCE_PUBLIC_DIR",
        "PUBLIC_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = load_settings()

    assert settings.data_dir == settings.project_root / "data"
    assert settings.public_dir == settings.project_root / "public"
    assert settings.public_base_url == ""


def test_settings_accept_environment_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Deployment settings can be supplied without a committed secret file."""
    monkeypatch.setenv("NEWS_INTELLIGENCE_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("NEWS_INTELLIGENCE_DATA_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("NEWS_INTELLIGENCE_PUBLIC_DIR", str(tmp_path / "site"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.test/news/")

    settings = load_settings()

    assert settings.project_root == tmp_path
    assert settings.data_dir == tmp_path / "private"
    assert settings.public_dir == tmp_path / "site"
    assert settings.public_base_url == "https://example.test/news"
