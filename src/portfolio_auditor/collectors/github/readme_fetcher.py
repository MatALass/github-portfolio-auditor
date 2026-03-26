from __future__ import annotations

from typing import Any

from portfolio_auditor.collectors.github.client import GitHubClient
from portfolio_auditor.settings import Settings, get_settings


def fetch_readme(owner: str, repo: str, settings: Settings | None = None) -> dict[str, Any] | None:
    resolved_settings = settings or get_settings()
    client = GitHubClient(resolved_settings)
    try:
        return client.get_repo_readme(f"{owner}/{repo}")
    finally:
        client.close()