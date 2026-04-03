"""
dashboard/optimizer.py

ROI-based action scoring and portfolio simulation, extracted from data_loader.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd

SEVERITY_ORDER = {"high": 3, "medium": 2, "low": 1}

ACTION_IMPACT_RULES: dict[str, dict[str, Any]] = {
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
        "fallback_points": 6.0,
        "effort_units": 2.0,
        "category": "documentation",
    },
    "Add a concise GitHub description.": {
        "penalty_codes": {"DESCRIPTION_MISSING"},
        "fallback_points": 1.0,
        "effort_units": 0.5,
        "category": "documentation",
    },
    "Expose a demo or homepage link when relevant.": {
        "penalty_codes": {"HOMEPAGE_MISSING", "DEMO_MISSING"},
        "fallback_points": 2.0,
        "effort_units": 0.5,
        "category": "portfolio_relevance",
    },
    "Clarify the portfolio positioning and business value.": {
        "penalty_codes": {"PORTFOLIO_VALUE_UNCLEAR"},
        "fallback_points": 3.0,
        "effort_units": 1.5,
        "category": "portfolio_relevance",
    },
    "Strengthen the technical depth of the implementation.": {
        "penalty_codes": {"TECHNICAL_DEPTH_LIMITED"},
        "fallback_points": 4.0,
        "effort_units": 3.0,
        "category": "technical_depth",
    },
    "Improve maintainability and code cleanliness.": {
        "penalty_codes": {"MAINTAINABILITY_WEAK"},
        "fallback_points": 3.0,
        "effort_units": 2.0,
        "category": "maintainability",
    },
}


def repo_penalty_points(score_entry: dict[str, Any]) -> dict[str, float]:
    result: dict[str, float] = {}
    for penalty in score_entry.get("penalties", []) or []:
        code = str(penalty.get("code", "")).strip()
        if not code:
            continue
        result[code] = result.get(code, 0.0) + float(penalty.get("points", 0.0) or 0.0)
    return result


def estimate_action_impact(
    action_text: str,
    review: dict[str, Any],
    score_entry: dict[str, Any],
    repo_row: dict[str, Any],
) -> dict[str, Any]:
    rule = ACTION_IMPACT_RULES.get(
        action_text,
        {
            "penalty_codes": set(),
            "fallback_points": 2.0,
            "effort_units": 2.0,
            "category": "general",
        },
    )

    penalty_index = repo_penalty_points(score_entry)

    review_matched_codes = [
        str(code).strip()
        for code in (review.get("matched_penalty_codes", []) or [])
        if str(code).strip()
    ]

    if review_matched_codes:
        matched_codes = [code for code in review_matched_codes if code in rule["penalty_codes"]]
    else:
        matched_codes = [code for code in penalty_index if code in rule["penalty_codes"]]

    estimated_points = round(sum(penalty_index.get(code, 0.0) for code in matched_codes), 2)

    if estimated_points <= 0 and action_text == "Write a complete README.":
        readme_length = int(repo_row.get("readme_length", 0) or 0)
        if readme_length == 0:
            estimated_points = float(rule["fallback_points"])

    elif estimated_points <= 0 and action_text == "Add a concise GitHub description.":
        description = str(repo_row.get("description") or "").strip()
        if not description:
            estimated_points = float(rule["fallback_points"])

    elif estimated_points <= 0 and action_text == "Expose a demo or homepage link when relevant.":
        homepage = str(repo_row.get("homepage") or "").strip()
        if not homepage:
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


def derive_repo_optimizer_fields(
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
        enriched = estimate_action_impact(
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
    score_ceiling = round(
        min(100.0, float(repo_row.get("global_score", 0.0)) + total_recoverable), 2
    )
    top_opportunity = opportunities[0] if opportunities else None

    return {
        "opportunities": opportunities,
        "estimated_recoverable_points": total_recoverable,
        "score_ceiling": score_ceiling,
        "top_opportunity": top_opportunity,
    }


def build_next_actions(
    df: pd.DataFrame,
    review_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
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
                    "matched_penalty_codes": list(
                        opportunity.get("matched_penalty_codes", [])
                    ),
                }
            )

    ranked_actions: list[dict[str, Any]] = []
    for action_text in counter:
        repos = sorted(
            action_rows[action_text],
            key=lambda item: (
                0
                if item["decision_label"]
                in {"Highlight now", "Keep and improve", "Improve / reposition"}
                else 1,
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

    return sorted(
        ranked_actions,
        key=lambda item: (
            -item["roi"],
            -item["estimated_total_score_lift"],
            -item["affected_repo_count"],
            item["action"],
        ),
    )[:12]


def simulate_portfolio(
    df: pd.DataFrame,
    next_actions: list[dict[str, Any]],
    visible_repo_names: list[str],
) -> dict[str, Any]:
    visible_df = df[df["repo_name"].isin(visible_repo_names)].copy()
    current_quality = (
        round(float(visible_df["global_score"].mean()), 2) if not visible_df.empty else 0.0
    )
    selected_df = df[df["decision_group"].isin(["keep", "improve"])].copy()

    prioritized_actions = sorted(
        next_actions,
        key=lambda item: (-item["roi"], -item["estimated_total_score_lift"], item["action"]),
    )

    def _project_for_scope(scope_df: pd.DataFrame, top_n: int) -> float:
        if scope_df.empty:
            return 0.0

        repo_lifts: dict[str, float] = {row["repo_name"]: 0.0 for _, row in scope_df.iterrows()}

        for action in prioritized_actions[:top_n]:
            for repo in action["repos"]:
                repo_name = str(repo.get("repo_name"))
                if repo_name not in repo_lifts:
                    continue

                current_score = float(
                    scope_df.loc[scope_df["repo_name"] == repo_name, "global_score"].iloc[0]
                )
                ceiling = float(
                    scope_df.loc[scope_df["repo_name"] == repo_name, "score_ceiling"].iloc[0]
                )
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
    selected_scope_quality = (
        round(float(selected_df["global_score"].mean()), 2) if not selected_df.empty else 0.0
    )
    selected_scope_after_top_three = _project_for_scope(selected_df, 3)

    return {
        "current_quality": current_quality,
        "quality_after_top_1": top_one_quality,
        "quality_after_top_3": top_three_quality,
        "selected_scope_current": selected_scope_quality,
        "selected_scope_after_top_3": selected_scope_after_top_three,
        "top_actions": prioritized_actions[:3],
    }