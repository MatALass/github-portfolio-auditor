from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from portfolio_auditor.collectors.github.client import GitHubApiError, GitHubRateLimitError
from portfolio_auditor.collectors.github.collector import GitHubCollector
from portfolio_auditor.models.repo_metadata import (
    RepoEngagement,
    RepoFlags,
    RepoLanguageStats,
    RepoLinks,
    RepoMetadata,
    RepoOwner,
    RepoTimestamps,
    RepoTopics,
)
from portfolio_auditor.settings import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(tmp_path: Path) -> Settings:
    return Settings(
        workspace_dir=tmp_path / "data",
        raw_dir=tmp_path / "data" / "raw",
        interim_dir=tmp_path / "data" / "interim",
        processed_dir=tmp_path / "data" / "processed",
        processed_history_dir=tmp_path / "data" / "processed_history",
        github_raw_dir=tmp_path / "data" / "raw" / "github",
        clones_dir=tmp_path / "data" / "raw" / "clones",
        scans_dir=tmp_path / "data" / "interim" / "scans",
        scores_dir=tmp_path / "data" / "interim" / "scores",
        reviews_dir=tmp_path / "data" / "interim" / "reviews",
    )


def _make_raw_payload(name: str = "repo-a", owner: str = "alice") -> dict:
    return {
        "id": 1,
        "name": name,
        "full_name": f"{owner}/{name}",
        "description": "A test repo",
        "default_branch": "main",
        "size": 42,
        "owner": {"login": owner, "type": "User", "html_url": f"https://github.com/{owner}"},
        "private": False,
        "fork": False,
        "archived": False,
        "disabled": False,
        "is_template": False,
        "has_issues": True,
        "has_projects": False,
        "has_wiki": False,
        "has_pages": False,
        "has_discussions": False,
        "stargazers_count": 0,
        "watchers_count": 0,
        "forks_count": 0,
        "open_issues_count": 0,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-02T00:00:00Z",
        "pushed_at": "2025-01-03T00:00:00Z",
        "html_url": f"https://github.com/{owner}/{name}",
        "clone_url": f"https://github.com/{owner}/{name}.git",
        "topics": [],
    }


def _make_client(
    *,
    authenticated_login: str | None = None,
    user_repos: list[dict] | None = None,
    authenticated_repos: list[dict] | None = None,
    org_repos: list[dict] | None = None,
    get_org_raises: Exception | None = None,
) -> MagicMock:
    client = MagicMock()
    client.get_authenticated_login.return_value = authenticated_login

    if get_org_raises is not None:
        client.get_org.side_effect = get_org_raises
    else:
        client.get_org.return_value = {"login": "some-org"}

    client.list_user_repos.return_value = user_repos or []
    client.list_authenticated_user_repos.return_value = authenticated_repos or []
    client.list_org_repos.return_value = org_repos or []
    client.get_repo_languages.return_value = {}
    client.get_repo_readme.return_value = None
    return client


# ---------------------------------------------------------------------------
# Routing tests
# ---------------------------------------------------------------------------

class TestCollectorRouting:
    """Verify that _list_owner_repos calls the correct client method."""

    def test_authenticated_owner_uses_authenticated_endpoint(self, tmp_path: Path) -> None:
        """When the token login matches the owner, /user/repos must be used."""
        raw = [_make_raw_payload("my-repo", "alice")]
        client = _make_client(authenticated_login="alice", authenticated_repos=raw)
        collector = GitHubCollector(client, _make_settings(tmp_path))

        repos = collector.collect_owner_repos("alice")

        client.list_authenticated_user_repos.assert_called_once()
        client.list_user_repos.assert_not_called()
        client.list_org_repos.assert_not_called()
        assert len(repos) == 1
        assert repos[0].name == "my-repo"

    def test_authenticated_owner_case_insensitive(self, tmp_path: Path) -> None:
        """Login comparison must be case-insensitive."""
        raw = [_make_raw_payload("repo", "Alice")]
        client = _make_client(authenticated_login="Alice", authenticated_repos=raw)
        collector = GitHubCollector(client, _make_settings(tmp_path))

        repos = collector.collect_owner_repos("alice")

        client.list_authenticated_user_repos.assert_called_once()
        assert len(repos) == 1

    def test_different_owner_uses_public_user_endpoint(self, tmp_path: Path) -> None:
        """When token owner differs from requested owner, use public /users/:owner/repos."""
        raw = [_make_raw_payload("their-repo", "bob")]
        client = _make_client(
            authenticated_login="alice",
            user_repos=raw,
            get_org_raises=GitHubApiError("not an org"),
        )
        collector = GitHubCollector(client, _make_settings(tmp_path))

        repos = collector.collect_owner_repos("bob")

        client.list_user_repos.assert_called_once()
        client.list_authenticated_user_repos.assert_not_called()
        assert repos[0].owner.login == "bob"

    def test_no_token_falls_back_to_public_user_endpoint(self, tmp_path: Path) -> None:
        """Without a token, authenticated_login is None → public user listing."""
        raw = [_make_raw_payload("public-repo", "charlie")]
        client = _make_client(
            authenticated_login=None,
            user_repos=raw,
            get_org_raises=GitHubApiError("not an org"),
        )
        collector = GitHubCollector(client, _make_settings(tmp_path))

        repos = collector.collect_owner_repos("charlie")

        client.list_user_repos.assert_called_once()
        client.list_authenticated_user_repos.assert_not_called()
        assert repos[0].name == "public-repo"

    def test_org_owner_uses_org_endpoint(self, tmp_path: Path) -> None:
        """When the owner is detected as an org, list_org_repos must be called."""
        raw = [_make_raw_payload("org-repo", "acme-corp")]
        client = _make_client(
            authenticated_login="alice",
            org_repos=raw,
            # get_org does NOT raise → owner is an org
        )
        collector = GitHubCollector(client, _make_settings(tmp_path))

        repos = collector.collect_owner_repos("acme-corp")

        client.list_org_repos.assert_called_once()
        client.list_user_repos.assert_not_called()
        assert repos[0].name == "org-repo"

    def test_new_repo_is_included_after_fresh_fetch(self, tmp_path: Path) -> None:
        """
        Regression: a repo created after the last cached snapshot must appear
        in results when a live fetch is performed (not the cache).
        """
        old_repo = _make_raw_payload("old-repo", "alice")
        new_repo = _make_raw_payload("new-repo", "alice")
        new_repo["id"] = 2

        client = _make_client(
            authenticated_login="alice",
            authenticated_repos=[old_repo, new_repo],
        )
        settings = _make_settings(tmp_path)
        collector = GitHubCollector(client, settings)

        # Seed an outdated cache that only knows about old-repo.
        from portfolio_auditor.models.repo_metadata import RepoMetadata
        old_meta = collector._parse_repo_payload(old_repo)
        collector.persist_raw_owner_snapshot("alice", [old_meta])

        repos = collector.collect_owner_repos("alice")
        repo_names = {r.name for r in repos}

        assert "new-repo" in repo_names, (
            "new-repo must be picked up from the live API, not the stale cache"
        )
        assert "old-repo" in repo_names


# ---------------------------------------------------------------------------
# Rate-limit fallback tests
# ---------------------------------------------------------------------------

class TestRateLimitFallback:
    def test_falls_back_to_snapshot_on_rate_limit(self, tmp_path: Path) -> None:
        """On GitHubRateLimitError the collector must load the on-disk snapshot."""
        settings = _make_settings(tmp_path)
        settings.ensure_directories()

        client = MagicMock()
        client.get_authenticated_login.return_value = "alice"
        client.list_authenticated_user_repos.side_effect = GitHubRateLimitError("rate limit exceeded")

        collector = GitHubCollector(client, settings)

        # Write a cached snapshot manually.
        from portfolio_auditor.models.repo_metadata import RepoMetadata
        cached_repo = collector._parse_repo_payload(_make_raw_payload("cached-repo", "alice"))
        collector.persist_raw_owner_snapshot("alice", [cached_repo])

        repos = collector.collect_owner_repos("alice")

        assert len(repos) == 1
        assert repos[0].name == "cached-repo"

    def test_raises_when_rate_limited_and_no_cache(self, tmp_path: Path) -> None:
        """Rate limit with no cache on disk must re-raise GitHubRateLimitError."""
        settings = _make_settings(tmp_path)
        settings.ensure_directories()

        client = MagicMock()
        client.get_authenticated_login.return_value = "alice"
        client.list_authenticated_user_repos.side_effect = GitHubRateLimitError("rate limit exceeded")

        collector = GitHubCollector(client, settings)

        with pytest.raises(GitHubRateLimitError):
            collector.collect_owner_repos("alice")