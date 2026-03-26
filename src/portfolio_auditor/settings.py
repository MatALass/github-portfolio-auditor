from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application settings.

    Environment variables should be defined in a local .env file or in the shell.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "github-portfolio-auditor"
    app_env: str = "development"
    log_level: str = "INFO"

    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")
    github_api_base_url: str = "https://api.github.com"
    github_clone_protocol: str = "https"
    github_request_timeout_seconds: float = 30.0
    github_max_repos_per_page: int = 100
    github_excluded_repo_names: str = "github-portfolio-auditor"

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    llm_enabled: bool = False

    workspace_dir: Path = Path("data")
    raw_dir: Path = Path("data/raw")
    interim_dir: Path = Path("data/interim")
    processed_dir: Path = Path("data/processed")
    processed_history_dir: Path = Path("data/processed_history")

    github_raw_dir: Path = Path("data/raw/github")
    clones_dir: Path = Path("data/raw/clones")
    scans_dir: Path = Path("data/interim/scans")
    scores_dir: Path = Path("data/interim/scores")
    reviews_dir: Path = Path("data/interim/reviews")

    github_owner: str | None = None
    include_forks: bool = True
    include_archived: bool = True
    max_repos: int | None = None

    @property
    def github_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": self.app_name,
        }
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"
        return headers

    @property
    def resolved_workspace_dir(self) -> Path:
        return self.workspace_dir.resolve()

    @property
    def data_dir(self) -> Path:
        """
        Backward-compatible alias kept for older modules and scripts.
        """
        return self.workspace_dir

    @property
    def normalized_excluded_repo_names(self) -> set[str]:
        values = {
            item.strip().lower()
            for item in self.github_excluded_repo_names.split(",")
            if item.strip()
        }
        values.add(self.app_name.strip().lower())
        return values

    def ensure_directories(self) -> None:
        directories = [
            self.workspace_dir,
            self.raw_dir,
            self.interim_dir,
            self.processed_dir,
            self.processed_history_dir,
            self.github_raw_dir,
            self.clones_dir,
            self.scans_dir,
            self.scores_dir,
            self.reviews_dir,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def get_repo_clone_path(self, repo_full_name: str) -> Path:
        """
        Example:
            'MatALass/repo_auditor' -> data/raw/clones/MatALass__repo_auditor
        """
        safe_name = repo_full_name.replace("/", "__")
        return self.clones_dir / safe_name

    def get_processed_owner_dir(self, owner: str) -> Path:
        return self.processed_dir / owner

    def get_processed_history_owner_dir(self, owner: str) -> Path:
        return self.processed_history_dir / owner

    def should_use_ssh_for_clone(self) -> bool:
        return self.github_clone_protocol.strip().lower() == "ssh"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings


def reset_settings_cache() -> None:
    """
    Useful for tests and live dashboard refreshes after environment changes.
    """
    get_settings.cache_clear()


def get_env_bool(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "y", "on"}
