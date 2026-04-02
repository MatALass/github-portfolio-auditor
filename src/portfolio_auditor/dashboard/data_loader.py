"""
dashboard/data_loader.py

Thin orchestration layer: loads JSON artifacts, builds the DataFrame, and
delegates metric/optimizer/comparison logic to dedicated sub-modules.

Sub-module responsibilities
---------------------------
metrics.py    — overview KPI computation
optimizer.py  — ROI-based action scoring, next-actions ranking, simulation
history.py    — snapshot persistence helpers (unchanged)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from portfolio_auditor.dashboard.history import latest_snapshot_dir, load_snapshot_meta
from portfolio_auditor.dashboard.metrics import compute_overview_metrics, selection_repo_full_names
from portfolio_auditor.dashboard.optimizer import (
    build_next_actions,
    derive_repo_optimizer_fields,
    simulate_portfolio,
)
from portfolio_auditor.settings import get_settings

PROCESSED_DIR = Path("data/processed")

DECISION_LABEL_MAP = {
    "FEATURE_NOW": "Highlight now",
    "KEEP_AND_IMPROVE": "Keep and improve",
    "MERGE_OR_REPOSITION": "Improve / reposition",
    "ARCHIVE_PUBLIC": "Archive public",
    "MAKE_PRIVATE": "Make private",
}

DECISION_GROUP_MAP = {
    "FEATURE_NOW": "keep",
    "KEEP_AND_IMPROVE": "keep",
    "MERGE_OR_REPOSITION": "improve",
    "ARCHIVE_PUBLIC": "discard",
    "MAKE_PRIVATE": "discard",
}


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
    comparison_summary: dict[str, Any] | None
    comparison_df: pd.DataFrame | None


class DashboardDataError(RuntimeError):
    """Raised when the processed artifacts required by the dashboard are invalid."""


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise DashboardDataError(f"Required artifact is missing: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_optional_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def discover_owners(processed_dir: Path = PROCESSED_DIR) -> list[str]:
    if not processed_dir.exists():
        return []
    return sorted(entry.name for entry in processed_dir.iterdir() if entry.is_dir())


def _index_by_repo_name(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in items:
        repo_name = item.get("repo_name")
        if isinstance(repo_name, str) and repo_name:
            index[repo_name] = item
    return index


# ---------------------------------------------------------------------------
# DataFrame construction
# ---------------------------------------------------------------------------


def _build_repo_dataframe(
    ranking: list[dict[str, Any]],
    review_index: dict[str, dict[str, Any]],
    score_index: dict[str, dict[str, Any]],
    scan_index: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    df = pd.DataFrame(ranking).copy()
    if df.empty:
        raise DashboardDataError(
            "ranking.json is empty. Run the pipeline before launching the dashboard."
        )

    df["decision_label"] = df["portfolio_decision"].map(DECISION_LABEL_MAP).fillna(df["portfolio_decision"])
    df["decision_group"] = df["portfolio_decision"].map(DECISION_GROUP_MAP).fillna("review")
    df["global_score"] = pd.to_numeric(df["global_score"], errors="coerce").fillna(0.0)
    df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(0.0)
    df["stars"] = pd.to_numeric(df.get("stars", 0), errors="coerce").fillna(0).astype(int)
    df["forks"] = pd.to_numeric(df.get("forks", 0), errors="coerce").fillna(0).astype(int)
    df["primary_language"] = df["primary_language"].fillna("Unknown")
    df["redundancy_status"] = df["redundancy_status"].fillna("UNKNOWN")
    df["overlap_cluster_id"] = df["overlap_cluster_id"].fillna("-")

    quick_win_counts: list[int] = []
    blockers: list[int] = []
    issues_count: list[int] = []
    next_actions: list[str] = []
    estimated_recoverable_points: list[float] = []
    score_ceiling: list[float] = []
    action_roi: list[float] = []
    optimizer_payloads: list[list[dict[str, Any]]] = []

    for row in df.to_dict(orient="records"):
        repo_name = str(row["repo_name"])
        review = review_index.get(repo_name, {})
        score_entry = score_index.get(repo_name, {})
        scan = scan_index.get(repo_name, {})

        quick_wins = review.get("quick_wins", []) or []
        blockers_list = review.get("blockers", []) or []
        issues = scan.get("issues", []) or []

        optimizer = derive_repo_optimizer_fields(review, score_entry, row)
        opportunities = optimizer["opportunities"]
        top_opportunity = optimizer["top_opportunity"]

        quick_win_counts.append(len(quick_wins))
        blockers.append(len(blockers_list))
        issues_count.append(len(issues))
        optimizer_payloads.append(opportunities)
        estimated_recoverable_points.append(float(optimizer["estimated_recoverable_points"]))
        score_ceiling.append(float(optimizer["score_ceiling"]))
        action_roi.append(float(top_opportunity["roi"]) if top_opportunity else 0.0)

        if top_opportunity:
            next_actions.append(top_opportunity["text"])
        elif quick_wins:
            next_actions.append(str(quick_wins[0].get("text", "Review repository findings")))
        else:
            next_actions.append("Review repository findings")

    df["quick_wins_count"] = quick_win_counts
    df["blockers_count"] = blockers
    df["issues_count"] = issues_count
    df["next_action"] = next_actions
    df["estimated_recoverable_points"] = estimated_recoverable_points
    df["score_ceiling"] = score_ceiling
    df["top_action_roi"] = action_roi
    df["optimizer_payload"] = optimizer_payloads

    decision_weight = (
        df["decision_group"]
        .map({"keep": 3, "improve": 2, "discard": 1, "review": 0})
        .fillna(0)
    )
    score_weight = df["global_score"] / 100.0
    blocker_penalty = df["blockers_count"] * 0.05
    action_complexity_penalty = df["priority_actions_count"].fillna(0) * 0.015
    upside_bonus = df["estimated_recoverable_points"] * 0.2
    roi_bonus = df["top_action_roi"] * 0.25
    df["action_priority"] = (
        (decision_weight * 10)
        + (score_weight * 5)
        + upside_bonus
        + roi_bonus
        - blocker_penalty
        - action_complexity_penalty
    ).round(2)

    breakdown_totals: list[dict[str, float]] = []
    for repo_name in df["repo_name"]:
        score_entry = score_index.get(repo_name, {})
        breakdown_totals.append(score_entry.get("breakdown", {}) or {})

    categories = [
        "architecture_structure",
        "documentation_delivery",
        "testing_reliability",
        "technical_depth",
        "portfolio_relevance",
        "maintainability_cleanliness",
    ]
    for category in categories:
        df[category] = [float(entry.get(category, 0.0)) for entry in breakdown_totals]

    return df.sort_values(["rank", "repo_name"], ascending=[True, True]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Historical comparison
# ---------------------------------------------------------------------------


def _build_comparison(
    current_df: pd.DataFrame, owner: str
) -> tuple[dict[str, Any] | None, pd.DataFrame | None]:
    settings = get_settings()
    snapshot_dir = latest_snapshot_dir(owner, settings)
    if snapshot_dir is None:
        return None, None

    previous_ranking = _load_optional_json(snapshot_dir / "ranking.json")
    previous_selection = _load_optional_json(snapshot_dir / "portfolio_selection.json") or {}
    if not isinstance(previous_ranking, list):
        return None, None

    previous_df = pd.DataFrame(previous_ranking)
    if previous_df.empty:
        return None, None

    previous_df["global_score"] = pd.to_numeric(
        previous_df["global_score"], errors="coerce"
    ).fillna(0.0)
    previous_df = previous_df[
        ["repo_full_name", "repo_name", "global_score", "portfolio_decision"]
    ].copy()
    previous_df = previous_df.rename(
        columns={
            "repo_name": "repo_name_previous",
            "global_score": "previous_score",
            "portfolio_decision": "previous_decision",
        }
    )

    current_comp = current_df[
        ["repo_full_name", "repo_name", "global_score", "portfolio_decision", "decision_label"]
    ].copy()
    current_comp = current_comp.rename(
        columns={"global_score": "current_score", "portfolio_decision": "current_decision"}
    )

    merged = current_comp.merge(previous_df, on="repo_full_name", how="outer")
    merged["repo_name"] = merged["repo_name"].fillna(merged["repo_name_previous"])
    merged["current_score"] = pd.to_numeric(merged["current_score"], errors="coerce")
    merged["previous_score"] = pd.to_numeric(merged["previous_score"], errors="coerce")
    merged["score_delta"] = (
        merged["current_score"].fillna(0.0) - merged["previous_score"].fillna(0.0)
    ).round(2)

    status: list[str] = []
    for row in merged.to_dict(orient="records"):
        current_score = row.get("current_score")
        previous_score = row.get("previous_score")
        if pd.isna(previous_score):
            status.append("new")
        elif pd.isna(current_score):
            status.append("removed")
        elif row.get("score_delta", 0.0) > 0:
            status.append("improved")
        elif row.get("score_delta", 0.0) < 0:
            status.append("declined")
        else:
            status.append("unchanged")
    merged["change_status"] = status

    previous_visible_names = selection_repo_full_names(
        previous_selection, "featured_repos", "keep_visible_but_improve"
    )
    previous_visible = previous_df[previous_df["repo_full_name"].isin(previous_visible_names)]
    current_visible = current_df[current_df["decision_group"].isin(["keep", "improve"])]
    previous_quality = (
        round(float(previous_visible["previous_score"].mean()), 2)
        if not previous_visible.empty
        else 0.0
    )
    current_quality = (
        round(float(current_visible["global_score"].mean()), 2)
        if not current_visible.empty
        else 0.0
    )

    snapshot_meta = load_snapshot_meta(snapshot_dir)
    summary = {
        "snapshot_label": snapshot_dir.name,
        "snapshot_created_at_utc": snapshot_meta.get("created_at_utc"),
        "improved_count": int((merged["change_status"] == "improved").sum()),
        "declined_count": int((merged["change_status"] == "declined").sum()),
        "unchanged_count": int((merged["change_status"] == "unchanged").sum()),
        "new_count": int((merged["change_status"] == "new").sum()),
        "removed_count": int((merged["change_status"] == "removed").sum()),
        "net_score_delta": round(float(merged["score_delta"].fillna(0.0).sum()), 2),
        "current_selected_scope_avg": current_quality,
        "previous_selected_scope_avg": previous_quality,
        "selected_scope_delta": round(current_quality - previous_quality, 2),
        "top_improvements": merged[merged["change_status"] == "improved"]
        .sort_values("score_delta", ascending=False)
        .head(8)
        .to_dict(orient="records"),
        "top_declines": merged[merged["change_status"] == "declined"]
        .sort_values("score_delta", ascending=True)
        .head(8)
        .to_dict(orient="records"),
    }
    merged = merged.sort_values(
        ["change_status", "score_delta", "repo_name"], ascending=[True, False, True]
    ).reset_index(drop=True)
    return summary, merged


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def load_dashboard_data(owner: str) -> DashboardData:
    base_dir = PROCESSED_DIR / owner
    if not base_dir.exists():
        raise DashboardDataError(f"Owner artifacts directory does not exist: {base_dir}")

    ranking = _load_json(base_dir / "ranking.json")
    ranking_summary = _load_json(base_dir / "ranking_summary.json")
    portfolio_selection = _load_json(base_dir / "portfolio_selection.json")
    redundancy_analysis = _load_json(base_dir / "redundancy_analysis.json")
    repos_site_data = _load_json(base_dir / "repos_site_data.json")
    site_payload = _load_json(base_dir / "site_payload.json")
    repo_reviews = _load_json(base_dir / "repo_reviews.json")
    repo_scores = _load_json(base_dir / "repo_scores.json")
    repo_scans = _load_json(base_dir / "repo_scans.json")

    if not isinstance(ranking, list):
        raise DashboardDataError("ranking.json must contain a list of repositories.")

    review_index = _index_by_repo_name(repo_reviews)
    score_index = _index_by_repo_name(repo_scores)
    scan_index = _index_by_repo_name(repo_scans)

    repo_df = _build_repo_dataframe(ranking, review_index, score_index, scan_index)
    overview_metrics = compute_overview_metrics(
        repo_df, site_payload, portfolio_selection, redundancy_analysis
    )
    next_actions_list = build_next_actions(repo_df, review_index)
    optimizer_summary = simulate_portfolio(
        repo_df,
        next_actions_list,
        overview_metrics["visible_now_repo_names"],
    )
    comparison_summary, comparison_df = _build_comparison(repo_df, owner)

    return DashboardData(
        owner=owner,
        base_dir=base_dir,
        ranking=ranking,
        ranking_summary=ranking_summary,
        portfolio_selection=portfolio_selection,
        redundancy_analysis=redundancy_analysis,
        site_payload=site_payload,
        repos_site_data=repos_site_data,
        repo_reviews=repo_reviews,
        repo_scores=repo_scores,
        repo_scans=repo_scans,
        repo_df=repo_df,
        review_index=review_index,
        score_index=score_index,
        scan_index=scan_index,
        overview_metrics=overview_metrics,
        next_actions=next_actions_list,
        optimizer_summary=optimizer_summary,
        comparison_summary=comparison_summary,
        comparison_df=comparison_df,
    )
