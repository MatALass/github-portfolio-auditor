from __future__ import annotations

from datetime import datetime, timedelta, timezone

from portfolio_auditor.dashboard.repo_sync import compare_repo_states, should_refresh_audit
from portfolio_auditor.models.repo_metadata import RepoMetadata


def make_repo(name: str, *, owner: str = "MatALass", pushed_at: datetime | None = None) -> RepoMetadata:
    now = datetime(2026, 3, 31, 12, 0, tzinfo=timezone.utc)
    return RepoMetadata.model_validate(
        {
            "id": abs(hash(name)) % 100000 + 1,
            "name": name,
            "full_name": f"{owner}/{name}",
            "description": None,
            "default_branch": "main",
            "size_kb": 1,
            "owner": {"login": owner, "type": "User", "html_url": f"https://github.com/{owner}"},
            "flags": {
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
            },
            "engagement": {
                "stargazers_count": 0,
                "watchers_count": 0,
                "forks_count": 0,
                "open_issues_count": 0,
                "subscribers_count": 0,
                "network_count": 0,
            },
            "timestamps": {
                "created_at": now.isoformat(),
                "updated_at": (pushed_at or now).isoformat(),
                "pushed_at": (pushed_at or now).isoformat(),
            },
            "links": {
                "html_url": f"https://github.com/{owner}/{name}",
                "clone_url": f"https://github.com/{owner}/{name}.git",
                "ssh_url": f"git@github.com:{owner}/{name}.git",
                "homepage": None,
            },
            "topics": {"items": []},
            "language": "Python",
            "language_stats": {"languages": {"Python": 100}},
            "license": None,
            "readme_download_url": None,
        }
    )


def test_compare_repo_states_detects_new_removed_changed_and_modified_since_processed() -> None:
    checked_at = datetime(2026, 3, 31, 14, 0, tzinfo=timezone.utc)
    processed_at = datetime(2026, 3, 31, 10, 0, tzinfo=timezone.utc)

    cached_repos = [
        make_repo("alpha", pushed_at=datetime(2026, 3, 31, 9, 0, tzinfo=timezone.utc)),
        make_repo("beta", pushed_at=datetime(2026, 3, 31, 9, 30, tzinfo=timezone.utc)),
    ]
    live_repos = [
        make_repo("alpha", pushed_at=datetime(2026, 3, 31, 13, 0, tzinfo=timezone.utc)),
        make_repo("gamma", pushed_at=datetime(2026, 3, 31, 13, 30, tzinfo=timezone.utc)),
    ]

    delta = compare_repo_states(
        live_repos=live_repos,
        cached_repos=cached_repos,
        checked_at=checked_at,
        latest_processed_audit_at=processed_at,
    )

    assert delta.new_repos == ("gamma",)
    assert delta.removed_repos == ("beta",)
    assert delta.changed_repos == ("alpha",)
    assert delta.modified_since_processed == ("alpha", "gamma")
    assert delta.total_changed_count == 3


def test_should_refresh_audit_requires_verified_live_state() -> None:
    checked_at = datetime.now(timezone.utc)
    delta = compare_repo_states(
        live_repos=[make_repo("alpha")],
        cached_repos=[make_repo("alpha")],
        checked_at=checked_at,
        latest_processed_audit_at=checked_at - timedelta(days=1),
    )

    decision = should_refresh_audit(
        type("SyncResult", (), {"delta": delta, "verified_live": False})()
    )

    assert decision.should_refresh is False
    assert "could not be verified" in decision.reason.lower()
