"""Application paths and optional local settings."""

from dataclasses import dataclass
from os import environ
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Runtime settings resolved from the environment."""

    project_root: Path
    data_dir: Path
    public_dir: Path
    public_base_url: str


def load_settings() -> Settings:
    """Load optional settings, defaulting paths to this project checkout."""
    project_root = Path(
        environ.get("NEWS_INTELLIGENCE_PROJECT_ROOT", Path(__file__).parents[2])
    ).resolve()
    return Settings(
        project_root=project_root,
        data_dir=Path(
            environ.get("NEWS_INTELLIGENCE_DATA_DIR", project_root / "data")
        ).resolve(),
        public_dir=Path(
            environ.get("NEWS_INTELLIGENCE_PUBLIC_DIR", project_root / "public")
        ).resolve(),
        public_base_url=environ.get("PUBLIC_BASE_URL", "").rstrip("/"),
    )
