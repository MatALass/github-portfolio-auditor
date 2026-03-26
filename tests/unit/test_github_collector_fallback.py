from pathlib import Path

from portfolio_auditor.collectors.github.client import GitHubRateLimitError
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


class RateLimitedClient:
    def list_user_repos(self, username: str):
        raise GitHubRateLimitError("rate limit exceeded")

    def list_org_repos(self, org_name: str):
        raise AssertionError("org lookup should not be attempted after a rate limit error")

    def get_repo_languages(self, full_name: str):
        raise GitHubRateLimitError("rate limit exceeded")

    def get_repo_readme(self, full_name: str):
        raise GitHubRateLimitError("rate limit exceeded")


def build_repo() -> RepoMetadata:
    return RepoMetadata(
        id=1,
        name="example",
        full_name="user/example",
        description="Example project",
        default_branch="main",
        size_kb=10,
        owner=RepoOwner(login="user", type="User", html_url="https://github.com/user"),
        flags=RepoFlags(),
        engagement=RepoEngagement(),
        timestamps=RepoTimestamps(
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-02T00:00:00Z",
            pushed_at="2025-01-03T00:00:00Z",
        ),
        links=RepoLinks(
            html_url="https://github.com/user/example",
            clone_url="https://github.com/user/example.git",
        ),
        language="Python",
        language_stats=RepoLanguageStats(languages={"Python": 100}),
        topics=RepoTopics(items=["python"]),
        readme_download_url="https://raw.githubusercontent.com/user/example/main/README.md",
    )


def test_collect_owner_repos_falls_back_to_cached_snapshot(tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path / "data",
        raw_dir=tmp_path / "data" / "raw",
        interim_dir=tmp_path / "data" / "interim",
        processed_dir=tmp_path / "data" / "processed",
        github_raw_dir=tmp_path / "data" / "raw" / "github",
        clones_dir=tmp_path / "data" / "raw" / "clones",
        scans_dir=tmp_path / "data" / "interim" / "scans",
        scores_dir=tmp_path / "data" / "interim" / "scores",
        reviews_dir=tmp_path / "data" / "interim" / "reviews",
    )
    settings.ensure_directories()

    collector = GitHubCollector(RateLimitedClient(), settings)
    collector.persist_raw_owner_snapshot("user", [build_repo()])

    repos = collector.collect_owner_repos("user")

    assert len(repos) == 1
    assert repos[0].full_name == "user/example"


def test_enrich_repos_keeps_base_repo_on_rate_limit(tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path / "data",
        raw_dir=tmp_path / "data" / "raw",
        interim_dir=tmp_path / "data" / "interim",
        processed_dir=tmp_path / "data" / "processed",
        github_raw_dir=tmp_path / "data" / "raw" / "github",
        clones_dir=tmp_path / "data" / "raw" / "clones",
        scans_dir=tmp_path / "data" / "interim" / "scans",
        scores_dir=tmp_path / "data" / "interim" / "scores",
        reviews_dir=tmp_path / "data" / "interim" / "reviews",
    )
    settings.ensure_directories()

    collector = GitHubCollector(RateLimitedClient(), settings)
    repo = build_repo()

    enriched = collector.enrich_repos([repo])

    assert len(enriched) == 1
    assert enriched[0].full_name == repo.full_name
    assert enriched[0].readme_download_url == repo.readme_download_url