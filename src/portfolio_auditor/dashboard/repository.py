from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from portfolio_auditor.dashboard.artifact_reader import (
    DashboardArtifacts,
    DashboardDataError,
    load_dashboard_artifacts,
)
from portfolio_auditor.dashboard.metrics import (
    build_repo_dataframe,
    compute_overview_metrics,
    index_by_repo_name,
)
from portfolio_auditor.dashboard.optimizer import build_next_actions, simulate_portfolio


@dataclass(frozen=True)
class DashboardData:
    owner: str
    base_dir: Path
    ranking: list[dict[str, Any]]
    ranking_summary: dict[str, Any]
    portfolio_selection: dict[str, Any]
    redundancy_analysis: dict[str, Any]
    site_payload: dict[str, Any]
    repos_site_data: dict[str, Any]
    repo_reviews: list[dict[str, Any]]
    repo_scores: list[dict[str, Any]]
    repo_scans: list[dict[str, Any]]
    repo_df: pd.DataFrame
    review_index: dict[str, dict[str, Any]]
    score_index: dict[str, dict[str, Any]]
    scan_index: dict[str, dict[str, Any]]
    overview_metrics: dict[str, Any]
    next_actions: list[dict[str, Any]]
    optimizer_summary: dict[str, Any]


class DashboardRepository:
    def __init__(self, artifacts: DashboardArtifacts) -> None:
        self.artifacts = artifacts

    def build(self) -> DashboardData:
        review_index = index_by_repo_name(self.artifacts.repo_reviews)
        score_index = index_by_repo_name(self.artifacts.repo_scores)
        scan_index = index_by_repo_name(self.artifacts.repo_scans)

        try:
            repo_df = build_repo_dataframe(
                self.artifacts.ranking,
                review_index,
                score_index,
                scan_index,
            )
        except ValueError as exc:
            raise DashboardDataError(str(exc)) from exc

        overview_metrics = compute_overview_metrics(
            repo_df,
            self.artifacts.site_payload,
            self.artifacts.portfolio_selection,
            self.artifacts.redundancy_analysis,
        )
        next_actions = build_next_actions(repo_df, review_index)
        optimizer_summary = simulate_portfolio(
            repo_df,
            next_actions,
            overview_metrics["visible_now_repo_names"],
        )

        return DashboardData(
            owner=self.artifacts.owner,
            base_dir=self.artifacts.base_dir,
            ranking=self.artifacts.ranking,
            ranking_summary=self.artifacts.ranking_summary,
            portfolio_selection=self.artifacts.portfolio_selection,
            redundancy_analysis=self.artifacts.redundancy_analysis,
            site_payload=self.artifacts.site_payload,
            repos_site_data=self.artifacts.repos_site_data,
            repo_reviews=self.artifacts.repo_reviews,
            repo_scores=self.artifacts.repo_scores,
            repo_scans=self.artifacts.repo_scans,
            repo_df=repo_df,
            review_index=review_index,
            score_index=score_index,
            scan_index=scan_index,
            overview_metrics=overview_metrics,
            next_actions=next_actions,
            optimizer_summary=optimizer_summary,
        )


def load_dashboard_repository(owner: str) -> DashboardData:
    artifacts = load_dashboard_artifacts(owner)
    return DashboardRepository(artifacts).build()
