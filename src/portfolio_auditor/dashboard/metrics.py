from __future__ import annotations

"""
dashboard/metrics.py

Overview metric computation extracted from data_loader.
"""

from typing import Any

import pandas as pd


def selection_repo_full_names(selection: dict[str, Any], *keys: str) -> list[str]:
    """Collect repo full names from the given keys in the selection dict."""
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


def compute_overview_metrics(
    df: pd.DataFrame,
    site_payload: dict[str, Any],
    selection: dict[str, Any],
    redundancy: dict[str, Any],
) -> dict[str, Any]:
    """
    Compute the top-level portfolio overview metrics shown in the sidebar and
    Overview tab.
    """
    visible_now = set(selection_repo_full_names(selection, "featured_repos", "keep_visible_but_improve"))
    visible_df = df[df["repo_full_name"].isin(visible_now)]
    selected_df = df[df["decision_group"].isin(["keep", "improve"])]

    return {
        "total_repositories": int(len(df)),
        "portfolio_quality_score": round(float(visible_df["global_score"].mean()), 2)
        if not visible_df.empty
        else 0.0,
        "global_average_score": round(float(df["global_score"].mean()), 2),
        "median_score": round(float(df["global_score"].median()), 2),
        "selected_scope_average": round(float(selected_df["global_score"].mean()), 2)
        if not selected_df.empty
        else 0.0,
        "highlight_count": int(len(selection.get("featured_repos", []))),
        "keep_visible_count": int(len(selection.get("keep_visible_but_improve", []))),
        "improvement_backlog_count": int(len(selection.get("improvement_backlog", []))),
        "discard_count": int(
            len(selection.get("archive_candidates", []))
            + len(selection.get("private_candidates", []))
        ),
        "redundancy_clusters": int(len(redundancy.get("overlap_clusters", []))),
        "redundancy_pairs": int(len(redundancy.get("overlap_pairs", []))),
        "manager_summary": site_payload.get("overview", {}).get("manager_summary", ""),
        "visible_repo_count": int(len(visible_df)),
        "selected_repo_count": int(len(selected_df)),
        "visible_now_repo_names": visible_df["repo_name"].tolist(),
    }
