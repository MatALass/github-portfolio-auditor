from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from portfolio_auditor.dashboard.history import latest_snapshot_dir, load_snapshot_meta
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

SEVERITY_ORDER = {"high": 3, "medium": 2, "low": 1}

ACTION_IMPACT_RULES = {
    "Build a core automated test suite.": {
        "penalty_codes": {"NO_TESTS_DETECTED", "WEAK_TEST_BASELINE"},
        "fallback_points": 0.0,
        "effort_units": 3.0,
        "category": "testing",
    },
    "Run automated tests in CI.": {
        "penalty_codes": {"NO_TEST_CI"},
        "fallback_points": 0.0,
        "effort_units": 2.0,
        "category": "testing",
    },
    "Introduce a clearer source-code structure.": {
        "penalty_codes": {"MAIN_CODE_DIR_MISSING", "ROOT_TOO_CROWDED"},
        "fallback_points": 0.0,
        "effort_units": 2.5,
        "category": "architecture",
    },
    "Document exactly how to run and use the project.": {
        "penalty_codes": {"USAGE_MISSING", "README_MISSING", "README_TOO_SHORT"},
        "fallback_points": 0.0,
        "effort_units": 1.5,
        "category": "documentation",
    },
    "Write a complete README.": {
        "penalty_codes": {"README_MISSING", "README_TOO_SHORT", "USAGE_MISSING"},
        "fallback_points": 0.0,
        "effort_units": 2.0,
        "category": "documentation",
    },
    "Add and apply a proper .gitignore.": {
        "penalty_codes": {"PYCACHE_COMMITTED", "BUILD_ARTIFACTS_COMMITTED"},
        "fallback_points": 0.0,
        "effort_units": 1.0,
        "category": "hygiene",
    },
    "Delete committed __pycache__ directories.": {
        "penalty_codes": {"PYCACHE_COMMITTED"},
        "fallback_points": 0.0,
        "effort_units": 0.5,
        "category": "hygiene",
    },
    "Remove generated build/cache artifacts.": {
        "penalty_codes": {"BUILD_ARTIFACTS_COMMITTED"},
        "fallback_points": 0.0,
        "effort_units": 0.75,
        "category": "hygiene",
    },
    "Review large committed files and keep only necessary assets.": {
        "penalty_codes": {"OVERSIZED_FILES"},
        "fallback_points": 0.0,
        "effort_units": 1.5,
        "category": "hygiene",
    },
    "Expose a demo or homepage link when relevant.": {
        "penalty_codes": set(),
        "fallback_points": 1.5,
        "effort_units": 1.0,
        "category": "portfolio_signal",
    },
    "Add a concise GitHub description.": {
        "penalty_codes": set(),
        "fallback_points": 1.0,
        "effort_units": 0.5,
        "category": "portfolio_signal",
    },
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


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise DashboardDataError(f"Required artifact is missing: {path}")
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


def _selection_repo_full_names(selection: dict[str, Any], *keys: str) -> list[str]:
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


def _repo_penalty_points(score_entry: dict[str, Any]) -> dict[str, float]:
    result: dict[str, float] = {}
    for penalty in score_entry.get("penalties", []) or []:
        code = str(penalty.get("code", "")).strip()
        if not code:
            continue
        result[code] = result.get(code, 0.0) + float(penalty.get("points", 0.0) or 0.0)
    return result


def _estimate_action_impact(
    action_text: str,
    review: dict[str, Any],
    score_entry: dict[str, Any],
    repo_row: dict[str, Any],
) -> dict[str, Any]:
    rule = ACTION_IMPACT_RULES.get(
        action_text,
        {
            "penalty_codes": set(),
            "fallback_points": 0.75,
            "effort_units": 1.5,
            "category": "general",
        },
    )

    penalty_points = _repo_penalty_points(score_entry)
    matched_codes = sorted(code for code in rule["penalty_codes"] if penalty_points.get(code, 0.0) > 0)
    estimated_points = sum(penalty_points.get(code, 0.0) for code in matched_codes)

    if estimated_points <= 0 and action_text == "Expose a demo or homepage link when relevant.":
        homepage = str(repo_row.get("homepage") or "").strip()
        if not homepage:
            estimated_points = float(rule["fallback_points"])
    elif estimated_points <= 0 and action_text == "Add a concise GitHub description.":
        description = str(repo_row.get("description") or "").strip()
        if not description:
            estimated_points = float(rule["fallback_points"])
    elif estimated_points <= 0 and action_text not in ACTION_IMPACT_RULES:
        estimated_points = float(rule["fallback_points"])

    current_score = float(repo_row.get("global_score", 0.0) or 0.0)
    estimated_points = min(estimated_points, max(0.0, 100.0 - current_score))
    projected_score = min(100.0, current_score + estimated_points)
    effort_units = float(rule["effort_units"])
    roi = round(estimated_points / effort_units, 2) if effort_units > 0 else 0.0

    return {
        "text": action_text,
        "priority": str(review.get("priority", "medium")),
        "category": str(rule["category"]),
        "matched_penalty_codes": matched_codes,
        "estimated_score_lift": round(estimated_points, 2),
        "projected_score": round(projected_score, 2),
        "effort_units": round(effort_units, 2),
        "roi": roi,
    }


def _derive_repo_optimizer_fields(
    review: dict[str, Any],
    score_entry: dict[str, Any],
    repo_row: dict[str, Any],
) -> dict[str, Any]:
    actions = review.get("priority_actions", []) or []
    opportunities: list[dict[str, Any]] = []

    for action in actions:
        action_text = str(action.get("text", "")).strip()
        if not action_text:
            continue
        enriched = _estimate_action_impact(
            action_text=action_text,
            review=action,
            score_entry=score_entry,
            repo_row=repo_row,
        )
        opportunities.append(enriched)

    opportunities = sorted(
        opportunities,
        key=lambda item: (
            -item["roi"],
            -item["estimated_score_lift"],
            SEVERITY_ORDER.get(item["priority"], 0),
            item["text"],
        ),
    )

    total_recoverable = round(sum(item["estimated_score_lift"] for item in opportunities), 2)
    score_ceiling = round(min(100.0, float(repo_row.get("global_score", 0.0)) + total_recoverable), 2)
    top_opportunity = opportunities[0] if opportunities else None

    return {
        "opportunities": opportunities,
        "estimated_recoverable_points": total_recoverable,
        "score_ceiling": score_ceiling,
        "top_opportunity": top_opportunity,
    }


def _build_repo_dataframe(
    ranking: list[dict[str, Any]],
    review_index: dict[str, dict[str, Any]],
    score_index: dict[str, dict[str, Any]],
    scan_index: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    df = pd.DataFrame(ranking).copy()
    if df.empty:
        raise DashboardDataError("ranking.json is empty. Run the pipeline before launching the dashboard.")

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

        optimizer = _derive_repo_optimizer_fields(review, score_entry, row)
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


def _compute_overview_metrics(
    df: pd.DataFrame,
    site_payload: dict[str, Any],
    selection: dict[str, Any],
    redundancy: dict[str, Any],
) -> dict[str, Any]:
    visible_now = set(_selection_repo_full_names(selection, "featured_repos", "keep_visible_but_improve"))
    visible_df = df[df["repo_full_name"].isin(visible_now)]
    selected_df = df[df["decision_group"].isin(["keep", "improve"])]

    metrics = {
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
    return metrics


def _build_next_actions(df: pd.DataFrame, review_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    action_rows: dict[str, list[dict[str, Any]]] = {}
    repo_lookup = df.set_index("repo_name").to_dict(orient="index")

    for repo_name in review_index:
        repo_entry = repo_lookup.get(repo_name, {})
        opportunities = repo_entry.get("optimizer_payload", []) or []
        for opportunity in opportunities:
            text = str(opportunity.get("text", "")).strip()
            if not text:
                continue
            counter[text] += 1
            action_rows.setdefault(text, []).append(
                {
                    "repo_name": repo_name,
                    "repo_full_name": repo_entry.get("repo_full_name", repo_name),
                    "global_score": float(repo_entry.get("global_score", 0.0)),
                    "decision_label": str(repo_entry.get("decision_label", "Review")),
                    "estimated_score_lift": float(opportunity.get("estimated_score_lift", 0.0)),
                    "effort_units": float(opportunity.get("effort_units", 0.0)),
                    "roi": float(opportunity.get("roi", 0.0)),
                    "matched_penalty_codes": list(opportunity.get("matched_penalty_codes", [])),
                }
            )

    ranked_actions: list[dict[str, Any]] = []
    for action_text, _count in counter.most_common(12):
        repos = sorted(
            action_rows[action_text],
            key=lambda item: (
                0 if item["decision_label"] in {"Highlight now", "Keep and improve", "Improve / reposition"} else 1,
                -item["estimated_score_lift"],
                -item["roi"],
                item["global_score"],
            ),
        )
        total_lift = round(sum(item["estimated_score_lift"] for item in repos), 2)
        total_effort = round(sum(item["effort_units"] for item in repos), 2)
        roi = round(total_lift / total_effort, 2) if total_effort > 0 else 0.0
        ranked_actions.append(
            {
                "action": action_text,
                "affected_repo_count": len(repos),
                "estimated_total_score_lift": total_lift,
                "total_effort_units": total_effort,
                "roi": roi,
                "repos": repos[:6],
            }
        )
    return ranked_actions


def _simulate_portfolio(df: pd.DataFrame, next_actions: list[dict[str, Any]], visible_repo_names: list[str]) -> dict[str, Any]:
    visible_df = df[df["repo_name"].isin(visible_repo_names)].copy()
    current_quality = round(float(visible_df["global_score"].mean()), 2) if not visible_df.empty else 0.0
    selected_df = df[df["decision_group"].isin(["keep", "improve"])].copy()

    prioritized_actions = sorted(
        next_actions,
        key=lambda item: (-item["roi"], -item["estimated_total_score_lift"], item["action"]),
    )

    def _project_for_scope(scope_df: pd.DataFrame, top_n: int) -> float:
        if scope_df.empty:
            return 0.0
        repo_lifts: dict[str, float] = {row["repo_name"]: 0.0 for _, row in scope_df.iterrows()}
        applied_actions = prioritized_actions[:top_n]
        for action in applied_actions:
            for repo in action["repos"]:
                repo_name = str(repo.get("repo_name"))
                if repo_name not in repo_lifts:
                    continue
                current_score = float(scope_df.loc[scope_df["repo_name"] == repo_name, "global_score"].iloc[0])
                ceiling = float(scope_df.loc[scope_df["repo_name"] == repo_name, "score_ceiling"].iloc[0])
                remaining = max(0.0, ceiling - current_score - repo_lifts[repo_name])
                lift = min(float(repo.get("estimated_score_lift", 0.0)), remaining)
                repo_lifts[repo_name] += lift
        projected_scores = [
            min(100.0, float(row["global_score"]) + repo_lifts.get(str(row["repo_name"]), 0.0))
            for _, row in scope_df.iterrows()
        ]
        return round(sum(projected_scores) / len(projected_scores), 2)

    top_one_quality = _project_for_scope(visible_df, 1)
    top_three_quality = _project_for_scope(visible_df, 3)
    selected_scope_quality = round(float(selected_df["global_score"].mean()), 2) if not selected_df.empty else 0.0
    selected_scope_after_top_three = _project_for_scope(selected_df, 3)

    return {
        "current_quality": current_quality,
        "quality_after_top_1": top_one_quality,
        "quality_after_top_3": top_three_quality,
        "selected_scope_current": selected_scope_quality,
        "selected_scope_after_top_3": selected_scope_after_top_three,
        "top_actions": prioritized_actions[:3],
    }


def _load_optional_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _build_comparison(current_df: pd.DataFrame, owner: str) -> tuple[dict[str, Any] | None, pd.DataFrame | None]:
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

    previous_df["global_score"] = pd.to_numeric(previous_df["global_score"], errors="coerce").fillna(0.0)
    previous_df = previous_df[["repo_full_name", "repo_name", "global_score", "portfolio_decision"]].copy()
    previous_df = previous_df.rename(
        columns={
            "repo_name": "repo_name_previous",
            "global_score": "previous_score",
            "portfolio_decision": "previous_decision",
        }
    )

    current_comp = current_df[["repo_full_name", "repo_name", "global_score", "portfolio_decision", "decision_label"]].copy()
    current_comp = current_comp.rename(columns={"global_score": "current_score", "portfolio_decision": "current_decision"})

    merged = current_comp.merge(previous_df, on="repo_full_name", how="outer")
    merged["repo_name"] = merged["repo_name"].fillna(merged["repo_name_previous"])
    merged["current_score"] = pd.to_numeric(merged["current_score"], errors="coerce")
    merged["previous_score"] = pd.to_numeric(merged["previous_score"], errors="coerce")
    merged["score_delta"] = (merged["current_score"].fillna(0.0) - merged["previous_score"].fillna(0.0)).round(2)

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

    previous_visible_names = _selection_repo_full_names(previous_selection, "featured_repos", "keep_visible_but_improve")
    previous_visible = previous_df[previous_df["repo_full_name"].isin(previous_visible_names)]
    current_visible = current_df[current_df["decision_group"].isin(["keep", "improve"])]
    previous_quality = round(float(previous_visible["previous_score"].mean()), 2) if not previous_visible.empty else 0.0
    current_quality = round(float(current_visible["global_score"].mean()), 2) if not current_visible.empty else 0.0

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
        "top_improvements": merged[merged["change_status"] == "improved"].sort_values("score_delta", ascending=False).head(8).to_dict(orient="records"),
        "top_declines": merged[merged["change_status"] == "declined"].sort_values("score_delta", ascending=True).head(8).to_dict(orient="records"),
    }
    merged = merged.sort_values(["change_status", "score_delta", "repo_name"], ascending=[True, False, True]).reset_index(drop=True)
    return summary, merged


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
    overview_metrics = _compute_overview_metrics(repo_df, site_payload, portfolio_selection, redundancy_analysis)
    next_actions = _build_next_actions(repo_df, review_index)
    optimizer_summary = _simulate_portfolio(
        repo_df,
        next_actions,
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
        next_actions=next_actions,
        optimizer_summary=optimizer_summary,
        comparison_summary=comparison_summary,
        comparison_df=comparison_df,
    )