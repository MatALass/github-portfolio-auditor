from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from portfolio_auditor.collectors.github.client import (
    GitHubApiError,
    GitHubClient,
    GitHubRateLimitError,
)
from portfolio_auditor.models.repo_metadata import (
    RepoEngagement,
    RepoFlags,
    RepoLanguageStats,
    RepoLicense,
    RepoLinks,
    RepoMetadata,
    RepoOwner,
    RepoTimestamps,
    RepoTopics,
)
from portfolio_auditor.settings import Settings


class GitHubCollector:
    """
    Normalize GitHub API payloads into the project's canonical RepoMetadata model.

    Responsibilities:
    - collect repositories for a user or organization
    - apply project-level filtering rules
    - enrich repositories with language and README metadata
    - persist raw normalized snapshots for downstream reproducibility
    - fall back to cached normalized snapshots when GitHub rate limiting prevents live collection
    """

    def __init__(self, client: GitHubClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def collect_owner_repos(self, owner: str) -> list[RepoMetadata]:
        """
        Collect repositories for an owner.

        Important:
        - live GitHub API responses are parsed from raw GitHub payloads
        - cached fallback snapshots are already normalized RepoMetadata-shaped payloads
        """
        payloads, payload_kind = self._list_owner_repos(owner)

        if payload_kind == "normalized_snapshot":
            repos = [RepoMetadata.model_validate(item) for item in payloads]
        else:
            repos = [self._parse_repo_payload(item) for item in payloads]

        repos = self._apply_filters(repos)
        repos.sort(key=lambda repo: (repo.owner.login.lower(), repo.name.lower()))
        return repos

    def enrich_repos(self, repos: list[RepoMetadata]) -> list[RepoMetadata]:
        """
        Enrich repositories with optional GitHub-derived metadata.

        If the GitHub API is rate-limited during enrichment, keep the base metadata
        rather than failing the whole audit run.
        """
        enriched: list[RepoMetadata] = []

        for repo in repos:
            update_data: dict[str, Any] = {}

            try:
                languages = self.client.get_repo_languages(repo.full_name)
            except GitHubRateLimitError:
                enriched.append(repo)
                continue
            except GitHubApiError:
                languages = {}

            if languages:
                update_data["language_stats"] = RepoLanguageStats(languages=languages)
                if not repo.language:
                    update_data["language"] = self._compute_primary_language(languages)

            try:
                readme = self.client.get_repo_readme(repo.full_name)
            except GitHubRateLimitError:
                readme = None
            except GitHubApiError:
                readme = None

            if readme and isinstance(readme.get("download_url"), str):
                update_data["readme_download_url"] = readme["download_url"].strip() or None

            if update_data:
                merged = repo.model_dump(mode="python")
                merged.update(update_data)
                enriched.append(RepoMetadata.model_validate(merged))
            else:
                enriched.append(repo)

        return enriched

    def persist_raw_owner_snapshot(self, owner: str, repos: list[RepoMetadata]) -> Path:
        output_path = self.get_raw_owner_snapshot_path(owner)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            self._serialize_repo_list(repos),
            encoding="utf-8",
        )
        return output_path

    def load_raw_owner_snapshot(self, owner: str) -> list[RepoMetadata]:
        snapshot_path = self.get_raw_owner_snapshot_path(owner)
        if not snapshot_path.exists():
            raise FileNotFoundError(
                f"No cached GitHub snapshot found for owner '{owner}' at {snapshot_path}."
            )

        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(
                f"Cached GitHub snapshot for owner '{owner}' is not a valid list payload."
            )

        repos = [RepoMetadata.model_validate(item) for item in payload]
        repos = self._apply_filters(repos)
        repos.sort(key=lambda repo: (repo.owner.login.lower(), repo.name.lower()))
        return repos

    def get_raw_owner_snapshot_path(self, owner: str) -> Path:
        return self.settings.github_raw_dir / f"{owner}_repos.json"

    def has_raw_owner_snapshot(self, owner: str) -> bool:
        return self.get_raw_owner_snapshot_path(owner).exists()

    def _list_owner_repos(self, owner: str) -> tuple[list[dict[str, Any]], str]:
        """
        Fetch the repository list for an owner from the GitHub API.

        Strategy:
        - If a GitHub token is present and matches the owner login, use the
          authenticated /user/repos endpoint so private repos are included.
        - Otherwise, probe for an organisation first; fall back to a public
          user listing on 404.
        - On rate-limit, fall back to the on-disk normalized snapshot.

        Returns:
            (payloads, payload_kind)

        payload_kind:
            - "github_api": raw GitHub API repository payloads
            - "normalized_snapshot": cached normalized RepoMetadata payloads
        """
        authenticated_login: str | None = None
        try:
            authenticated_login = self.client.get_authenticated_login()
        except Exception:
            pass

        include_private = bool(authenticated_login and authenticated_login.lower() == owner.lower())

        try:
            if include_private:
                # Authenticated owner — /user/repos returns private repos too.
                payloads = self.client.list_authenticated_user_repos()
            else:
                # Unknown owner: try org first when the client supports org probing,
                # otherwise fall back directly to the public user listing.
                if hasattr(self.client, "get_org") and hasattr(self.client, "list_org_repos"):
                    try:
                        self.client.get_org(owner)
                        payloads = self.client.list_org_repos(owner)
                    except GitHubApiError:
                        payloads = self.client.list_user_repos(owner)
                else:
                    payloads = self.client.list_user_repos(owner)

            return payloads, "github_api"

        except GitHubRateLimitError:
            snapshot_path = self.get_raw_owner_snapshot_path(owner)
            if snapshot_path.exists():
                cached_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
                if isinstance(cached_payload, list):
                    return cached_payload, "normalized_snapshot"
            raise

    def _apply_filters(self, repos: list[RepoMetadata]) -> list[RepoMetadata]:
        filtered = repos
        excluded_names = self.settings.normalized_excluded_repo_names

        filtered = [
            repo
            for repo in filtered
            if repo.name.lower() != repo.owner.login.lower()
            and repo.name.lower() not in excluded_names
        ]

        if not self.settings.include_forks:
            filtered = [repo for repo in filtered if not repo.flags.fork]

        if not self.settings.include_archived:
            filtered = [repo for repo in filtered if not repo.flags.archived]

        if self.settings.max_repos is not None:
            filtered = filtered[: self.settings.max_repos]

        return filtered

    @staticmethod
    def _compute_primary_language(languages: dict[str, int]) -> str | None:
        if not languages:
            return None
        return max(languages.items(), key=lambda item: item[1])[0]

    @staticmethod
    def _serialize_repo_list(repos: list[RepoMetadata]) -> str:
        return json.dumps(
            [repo.model_dump(mode="json") for repo in repos],
            indent=2,
            ensure_ascii=False,
        )

    @staticmethod
    def _parse_repo_payload(payload: dict[str, Any]) -> RepoMetadata:
        owner_payload = payload.get("owner") or {}
        license_payload = payload.get("license") or None

        raw_topics = payload.get("topics") or []
        if isinstance(raw_topics, dict):
            topic_items = raw_topics.get("items", [])
        else:
            topic_items = raw_topics

        raw_language_stats = payload.get("language_stats") or {}
        if isinstance(raw_language_stats, dict):
            language_map = raw_language_stats.get("languages", {})
        else:
            language_map = {}

        return RepoMetadata(
            id=int(payload["id"]),
            name=str(payload["name"]),
            full_name=str(payload["full_name"]),
            description=payload.get("description"),
            default_branch=str(payload.get("default_branch") or "main"),
            size_kb=int(payload.get("size") or 0),
            owner=RepoOwner(
                login=str(owner_payload.get("login") or "unknown"),
                type=str(owner_payload.get("type") or "User"),
                html_url=owner_payload.get("html_url"),
            ),
            flags=RepoFlags(
                private=bool(payload.get("private", False)),
                fork=bool(payload.get("fork", False)),
                archived=bool(payload.get("archived", False)),
                disabled=bool(payload.get("disabled", False)),
                is_template=bool(payload.get("is_template", False)),
                has_issues=bool(payload.get("has_issues", True)),
                has_projects=bool(payload.get("has_projects", False)),
                has_wiki=bool(payload.get("has_wiki", False)),
                has_pages=bool(payload.get("has_pages", False)),
                has_discussions=bool(payload.get("has_discussions", False)),
            ),
            engagement=RepoEngagement(
                stargazers_count=payload.get("stargazers_count", 0),
                watchers_count=payload.get("watchers_count", 0),
                forks_count=payload.get("forks_count", 0),
                open_issues_count=payload.get("open_issues_count", 0),
                subscribers_count=payload.get("subscribers_count"),
                network_count=payload.get("network_count"),
            ),
            timestamps=RepoTimestamps(
                created_at=payload["created_at"],
                updated_at=payload["updated_at"],
                pushed_at=payload.get("pushed_at"),
            ),
            links=RepoLinks(
                html_url=payload["html_url"],
                clone_url=payload.get("clone_url"),
                ssh_url=payload.get("ssh_url"),
                homepage=payload.get("homepage") or None,
            ),
            language=payload.get("language") or None,
            language_stats=RepoLanguageStats(languages=language_map),
            topics=RepoTopics(items=topic_items),
            license=(
                RepoLicense(
                    key=license_payload.get("key"),
                    name=license_payload.get("name"),
                    spdx_id=license_payload.get("spdx_id"),
                    url=license_payload.get("url"),
                )
                if license_payload
                else None
            ),
            readme_download_url=payload.get("readme_download_url"),
        )
