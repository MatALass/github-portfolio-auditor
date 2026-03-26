from __future__ import annotations

from portfolio_auditor.collectors.github.client import GitHubClient
from portfolio_auditor.settings import Settings, get_settings


def fetch_languages(owner: str, repo: str, settings: Settings | None = None) -> dict[str, int]:
    resolved_settings = settings or get_settings()
    client = GitHubClient(resolved_settings)
    try:
        return client.get_repo_languages(f"{owner}/{repo}")
    finally:
        client.close()