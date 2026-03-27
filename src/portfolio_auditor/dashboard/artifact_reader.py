from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROCESSED_DIR = Path("data/processed")
REQUIRED_ARTIFACT_FILES = (
    "ranking.json",
    "ranking_summary.json",
    "portfolio_selection.json",
    "redundancy_analysis.json",
    "repos_site_data.json",
    "site_payload.json",
    "repo_reviews.json",
    "repo_scores.json",
    "repo_scans.json",
)


class DashboardDataError(RuntimeError):
    """Raised when the processed artifacts required by the dashboard are invalid."""


@dataclass(frozen=True, slots=True)
class DashboardArtifacts:
    owner: str
    base_dir: Path
    ranking: list[dict[str, Any]]
    ranking_summary: dict[str, Any]
    portfolio_selection: dict[str, Any]
    redundancy_analysis: dict[str, Any]
    repos_site_data: dict[str, Any]
    site_payload: dict[str, Any]
    repo_reviews: list[dict[str, Any]]
    repo_scores: list[dict[str, Any]]
    repo_scans: list[dict[str, Any]]


def load_json_artifact(path: Path) -> Any:
    if not path.exists():
        raise DashboardDataError(f"Required artifact is missing: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def discover_owners(processed_dir: Path = PROCESSED_DIR) -> list[str]:
    if not processed_dir.exists():
        return []
    return sorted(entry.name for entry in processed_dir.iterdir() if entry.is_dir())


def load_dashboard_artifacts(
    owner: str,
    *,
    processed_dir: Path = PROCESSED_DIR,
) -> DashboardArtifacts:
    base_dir = processed_dir / owner
    if not base_dir.exists():
        raise DashboardDataError(f"Owner artifacts directory does not exist: {base_dir}")

    loaded: dict[str, Any] = {}
    for file_name in REQUIRED_ARTIFACT_FILES:
        loaded[file_name] = load_json_artifact(base_dir / file_name)

    ranking = loaded["ranking.json"]
    if not isinstance(ranking, list):
        raise DashboardDataError("ranking.json must contain a list of repositories.")

    return DashboardArtifacts(
        owner=owner,
        base_dir=base_dir,
        ranking=ranking,
        ranking_summary=loaded["ranking_summary.json"],
        portfolio_selection=loaded["portfolio_selection.json"],
        redundancy_analysis=loaded["redundancy_analysis.json"],
        repos_site_data=loaded["repos_site_data.json"],
        site_payload=loaded["site_payload.json"],
        repo_reviews=loaded["repo_reviews.json"],
        repo_scores=loaded["repo_scores.json"],
        repo_scans=loaded["repo_scans.json"],
    )
