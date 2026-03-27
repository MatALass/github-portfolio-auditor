from __future__ import annotations

from typing import Any

import pandas as pd

from portfolio_auditor.dashboard.optimizer import derive_repo_optimizer_fields

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


def index_by_repo_name(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in items:
        repo_name = item.get("repo_name")
        if isinstance(repo_name, str) and repo_name:
            index[repo_name] = item
    return index


def selection_repo_full_names(selection: dict[str, Any], *keys: str) -> list[str]:
    repo_full_names: list[str] = []
    for key in keys:
        for item in selection.get(key, []) or []:
            if isinstance(item, dict):
                repo_full_name = item.get("repo_full_name")
                if isinstance(repo_full_name, str) and repo_full_name:
                    repo_full_names.append(repo_full_name)
            elif isinstance(item, str) and item:
                repo_full_names.append(item)
    return list(dict.fromkeys(repo_full_names))


def build_repo_dataframe(
    ranking: list[dict[str, Any]],
    review_index: dict[str, dict[str, Any]],
    score_index: dict[str, dict[str, Any]],
    scan_index: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    df = pd.DataFrame(ranking).copy()
    if df.empty:
        raise ValueError("ranking.json is empty. Run the pipeline before launching the dashboard.")

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

    decision_weight = df["decision_group"].map({"keep": 3, "improve": 2, "discard": 1, "review": 0}).fillna(0)
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


def compute_overview_metrics(
    df: pd.DataFrame,
    site_payload: dict[str, Any],
    selection: dict[str, Any],
    redundancy: dict[str, Any],
) -> dict[str, Any]:
    visible_now = set(selection_repo_full_names(selection, "featured_repos", "keep_visible_but_improve"))
    visible_df = df[df["repo_full_name"].isin(visible_now)]
    selected_df = df[df["decision_group"].isin(["keep", "improve"])]

    return {
        "total_repositories": int(len(df)),
        "portfolio_quality_score": round(float(visible_df["global_score"].mean()), 2) if not visible_df.empty else 0.0,
        "global_average_score": round(float(df["global_score"].mean()), 2),
        "median_score": round(float(df["global_score"].median()), 2),
        "selected_scope_average": round(float(selected_df["global_score"].mean()), 2) if not selected_df.empty else 0.0,
        "highlight_count": int(len(selection.get("featured_repos", []))),
        "keep_visible_count": int(len(selection.get("keep_visible_but_improve", []))),
        "improvement_backlog_count": int(len(selection.get("improvement_backlog", []))),
        "discard_count": int(len(selection.get("archive_candidates", [])) + len(selection.get("private_candidates", []))),
        "redundancy_clusters": int(len(redundancy.get("overlap_clusters", []))),
        "redundancy_pairs": int(len(redundancy.get("overlap_pairs", []))),
        "manager_summary": site_payload.get("overview", {}).get("manager_summary", ""),
        "visible_repo_count": int(len(visible_df)),
        "selected_repo_count": int(len(selected_df)),
        "visible_now_repo_names": visible_df["repo_name"].tolist(),
    }
