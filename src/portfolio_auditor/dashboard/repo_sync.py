from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from portfolio_auditor.collectors.github.client import GitHubApiError, GitHubClient
from portfolio_auditor.collectors.github.collector import GitHubCollector
from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.settings import Settings


@dataclass(frozen=True)
class RepoSnapshotState:
    repo_name: str
    full_name: str
    pushed_at: datetime | None
    updated_at: datetime
    is_private: bool
    is_archived: bool
    is_fork: bool


@dataclass(frozen=True)
class RepoSyncDelta:
    live_repo_count: int
    cached_repo_count: int
    new_repos: tuple[str, ...]
    removed_repos: tuple[str, ...]
    changed_repos: tuple[str, ...]
    modified_since_processed: tuple[str, ...]
    latest_live_push_at: datetime | None
    latest_cached_push_at: datetime | None
    latest_processed_audit_at: datetime | None
    checked_at: datetime

    @property
    def has_changes(self) -> bool:
        return bool(
            self.new_repos
            or self.removed_repos
            or self.changed_repos
            or self.modified_since_processed
        )

    @property
    def total_changed_count(self) -> int:
        repo_names = {
            *self.new_repos,
            *self.removed_repos,
            *self.changed_repos,
            *self.modified_since_processed,
        }
        return len(repo_names)


@dataclass(frozen=True)
class RepoSyncResult:
    owner: str
    delta: RepoSyncDelta
    source: str
    verified_live: bool
    warning: str | None = None


@dataclass(frozen=True)
class AuditDecision:
    should_refresh: bool
    reason: str


def build_repo_snapshot_state_map(repos: list[RepoMetadata]) -> dict[str, RepoSnapshotState]:
    return {
        repo.name: RepoSnapshotState(
            repo_name=repo.name,
            full_name=repo.full_name,
            pushed_at=repo.timestamps.pushed_at,
            updated_at=repo.timestamps.updated_at,
            is_private=repo.flags.private,
            is_archived=repo.flags.archived,
            is_fork=repo.flags.fork,
        )
        for repo in repos
    }


def fetch_live_repo_sync_result(owner: str, settings: Settings) -> RepoSyncResult:
    client = GitHubClient(settings)
    collector = GitHubCollector(client, settings)
    checked_at = datetime.now(timezone.utc)
    latest_processed_at = latest_processed_audit_timestamp(owner, settings)

    try:
        payloads, payload_kind = collector._list_owner_repos(owner)
        if payload_kind == "normalized_snapshot":
            live_repos = [RepoMetadata.model_validate(item) for item in payloads]
            live_repos = collector._apply_filters(live_repos)
            source = "cached_snapshot_fallback"
            verified_live = False
            warning = (
                "GitHub API was not queried live. The sync view is using the cached raw snapshot only, "
                "so brand-new repositories cannot be confirmed until live access succeeds."
            )
        else:
            live_repos = [collector._parse_repo_payload(item) for item in payloads]
            live_repos = collector._apply_filters(live_repos)
            source = "github_api"
            verified_live = True
            warning = None
    except GitHubApiError as exc:
        cached_repos = (
            collector.load_raw_owner_snapshot(owner)
            if collector.has_raw_owner_snapshot(owner)
            else []
        )
        delta = compare_repo_states(
            live_repos=cached_repos,
            cached_repos=cached_repos,
            checked_at=checked_at,
            latest_processed_audit_at=latest_processed_at,
        )
        return RepoSyncResult(
            owner=owner,
            delta=delta,
            source="cached_snapshot_fallback",
            verified_live=False,
            warning=(
                "GitHub live sync unavailable. Using the cached raw snapshot only. "
                f"Underlying error: {exc}"
            ),
        )
    finally:
        client.close()

    cached_repos = (
        collector.load_raw_owner_snapshot(owner) if collector.has_raw_owner_snapshot(owner) else []
    )
    delta = compare_repo_states(
        live_repos=live_repos,
        cached_repos=cached_repos,
        checked_at=checked_at,
        latest_processed_audit_at=latest_processed_at,
    )
    return RepoSyncResult(
        owner=owner,
        delta=delta,
        source=source,
        verified_live=verified_live,
        warning=warning,
    )


def compare_repo_states(
    *,
    live_repos: list[RepoMetadata],
    cached_repos: list[RepoMetadata],
    checked_at: datetime,
    latest_processed_audit_at: datetime | None = None,
) -> RepoSyncDelta:
    live_map = build_repo_snapshot_state_map(live_repos)
    cached_map = build_repo_snapshot_state_map(cached_repos)

    new_repos = sorted(set(live_map) - set(cached_map))
    removed_repos = sorted(set(cached_map) - set(live_map))

    changed_repos: list[str] = []
    for repo_name in sorted(set(live_map) & set(cached_map)):
        live = live_map[repo_name]
        cached = cached_map[repo_name]
        if (
            live.pushed_at != cached.pushed_at
            or live.updated_at != cached.updated_at
            or live.is_private != cached.is_private
            or live.is_archived != cached.is_archived
            or live.is_fork != cached.is_fork
        ):
            changed_repos.append(repo_name)

    modified_since_processed = _compute_modified_since_processed(
        live_map=live_map,
        latest_processed_audit_at=latest_processed_audit_at,
    )

    return RepoSyncDelta(
        live_repo_count=len(live_map),
        cached_repo_count=len(cached_map),
        new_repos=tuple(new_repos),
        removed_repos=tuple(removed_repos),
        changed_repos=tuple(changed_repos),
        modified_since_processed=tuple(modified_since_processed),
        latest_live_push_at=_latest_push_at(live_map.values()),
        latest_cached_push_at=_latest_push_at(cached_map.values()),
        latest_processed_audit_at=latest_processed_audit_at,
        checked_at=checked_at,
    )


def should_refresh_audit(sync_result: RepoSyncResult) -> AuditDecision:
    delta = sync_result.delta
    if not sync_result.verified_live:
        return AuditDecision(
            False,
            "Live GitHub state could not be verified. Refresh decisions are disabled until API access succeeds.",
        )
    if delta.new_repos:
        return AuditDecision(True, f"{len(delta.new_repos)} new repositories detected on GitHub.")
    if delta.removed_repos:
        return AuditDecision(
            True,
            f"{len(delta.removed_repos)} repositories were removed from GitHub or are no longer visible.",
        )
    if delta.modified_since_processed:
        return AuditDecision(
            True,
            f"{len(delta.modified_since_processed)} repositories were updated after the latest processed audit.",
        )
    if delta.changed_repos:
        return AuditDecision(
            True,
            f"{len(delta.changed_repos)} repositories changed since the last cached raw snapshot.",
        )
    return AuditDecision(False, "Live GitHub metadata matches the current processed snapshot.")


def latest_processed_audit_timestamp(owner: str, settings: Settings) -> datetime | None:
    ranking_path = settings.get_processed_owner_dir(owner) / "ranking.json"
    if not ranking_path.exists():
        return None
    return datetime.fromtimestamp(ranking_path.stat().st_mtime, tz=timezone.utc)


def latest_live_repo_push_timestamp(owner: str, settings: Settings) -> datetime | None:
    sync_result = fetch_live_repo_sync_result(owner, settings)
    return sync_result.delta.latest_live_push_at


def _compute_modified_since_processed(
    *,
    live_map: dict[str, RepoSnapshotState],
    latest_processed_audit_at: datetime | None,
) -> list[str]:
    if latest_processed_audit_at is None:
        return []

    modified_repo_names: list[str] = []
    for repo_name in sorted(live_map):
        repo = live_map[repo_name]
        last_change = repo.pushed_at or repo.updated_at
        if last_change > latest_processed_audit_at:
            modified_repo_names.append(repo_name)
    return modified_repo_names


def _latest_push_at(items: object) -> datetime | None:
    timestamps: list[datetime] = []
    for item in items:
        if isinstance(item, RepoSnapshotState):
            candidate = item.pushed_at or item.updated_at
            if candidate is not None:
                timestamps.append(candidate)
    if not timestamps:
        return None
    return max(timestamps)
