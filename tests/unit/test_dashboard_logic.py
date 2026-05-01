"""
tests/unit/test_dashboard_logic.py

Unit tests for dashboard/optimizer.py and dashboard/metrics.py.

These modules contain pure functions that operate on dicts and DataFrames,
so they can be tested without any filesystem or Streamlit dependency.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from portfolio_auditor.dashboard.metrics import (
    compute_overview_metrics,
    selection_repo_full_names,
)
from portfolio_auditor.dashboard.optimizer import (
    ACTION_IMPACT_RULES,
    SEVERITY_ORDER,
    build_next_actions,
    derive_repo_optimizer_fields,
    estimate_action_impact,
    repo_penalty_points,
    simulate_portfolio,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row(
    repo_name: str,
    global_score: float,
    decision: str = "KEEP_AND_IMPROVE",
    group: str = "keep",
    repo_full_name: str | None = None,
) -> dict[str, Any]:
    return {
        "repo_name": repo_name,
        "repo_full_name": repo_full_name or f"user/{repo_name}",
        "global_score": global_score,
        "portfolio_decision": decision,
        "decision_group": group,
        "decision_label": "Keep and improve",
        "rank": 1,
        "confidence": 0.8,
        "stars": 0,
        "forks": 0,
        "primary_language": "Python",
        "redundancy_status": "UNIQUE",
        "overlap_cluster_id": "-",
        "priority_actions_count": 0,
        "blockers_count": 0,
        "quick_wins_count": 0,
        "issues_count": 0,
        "next_action": "Review repository findings",
        "estimated_recoverable_points": 0.0,
        "score_ceiling": global_score,
        "top_action_roi": 0.0,
        "optimizer_payload": [],
        "action_priority": 5.0,
        "architecture_structure": 10.0,
        "documentation_delivery": 10.0,
        "testing_reliability": 8.0,
        "technical_depth": 8.0,
        "portfolio_relevance": 10.0,
        "maintainability_cleanliness": 6.0,
        "homepage": None,
        "description": "A repo",
    }


def _df(*rows: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


# ---------------------------------------------------------------------------
# metrics.py — selection_repo_full_names
# ---------------------------------------------------------------------------


class TestSelectionRepoFullNames:
    def test_extracts_from_dict_items(self) -> None:
        selection = {
            "featured_repos": [
                {"repo_full_name": "user/repo-a"},
                {"repo_full_name": "user/repo-b"},
            ]
        }
        names = selection_repo_full_names(selection, "featured_repos")
        assert names == ["user/repo-a", "user/repo-b"]

    def test_extracts_from_string_items(self) -> None:
        selection = {"featured_repos": ["user/repo-x", "user/repo-y"]}
        names = selection_repo_full_names(selection, "featured_repos")
        assert names == ["user/repo-x", "user/repo-y"]

    def test_deduplicates(self) -> None:
        selection = {
            "featured_repos": [{"repo_full_name": "user/repo-a"}],
            "keep_visible_but_improve": [{"repo_full_name": "user/repo-a"}],
        }
        names = selection_repo_full_names(selection, "featured_repos", "keep_visible_but_improve")
        assert names.count("user/repo-a") == 1

    def test_missing_key_returns_empty(self) -> None:
        assert selection_repo_full_names({}, "featured_repos") == []

    def test_none_list_returns_empty(self) -> None:
        selection: dict[str, Any] = {"featured_repos": None}
        assert selection_repo_full_names(selection, "featured_repos") == []


# ---------------------------------------------------------------------------
# metrics.py — compute_overview_metrics
# ---------------------------------------------------------------------------


class TestComputeOverviewMetrics:
    def _selection(self, featured: list[str], keep: list[str] | None = None) -> dict[str, Any]:
        return {
            "featured_repos": [{"repo_full_name": n} for n in featured],
            "keep_visible_but_improve": [{"repo_full_name": n} for n in (keep or [])],
            "improvement_backlog": [],
            "archive_candidates": [],
            "private_candidates": [],
        }

    def _site_payload(self) -> dict[str, Any]:
        return {"overview": {"manager_summary": "All good."}}

    def _redundancy(self) -> dict[str, Any]:
        return {"overlap_clusters": [], "overlap_pairs": []}

    def test_total_repositories_count(self) -> None:
        df = _df(_row("a", 80), _row("b", 70), _row("c", 50))
        metrics = compute_overview_metrics(
            df, self._site_payload(), self._selection([]), self._redundancy()
        )
        assert metrics["total_repositories"] == 3

    def test_highlight_count(self) -> None:
        df = _df(_row("a", 90, repo_full_name="user/a"), _row("b", 75, repo_full_name="user/b"))
        selection = self._selection(["user/a"])
        metrics = compute_overview_metrics(df, self._site_payload(), selection, self._redundancy())
        assert metrics["highlight_count"] == 1

    def test_portfolio_quality_score_is_mean_of_visible(self) -> None:
        df = _df(
            _row("a", 80.0, repo_full_name="user/a"),
            _row("b", 60.0, repo_full_name="user/b"),
            _row("c", 40.0, repo_full_name="user/c"),
        )
        selection = self._selection(["user/a", "user/b"])
        metrics = compute_overview_metrics(df, self._site_payload(), selection, self._redundancy())
        assert metrics["portfolio_quality_score"] == pytest.approx(70.0, abs=0.1)

    def test_zero_score_when_no_visible_repos(self) -> None:
        df = _df(_row("a", 80.0, repo_full_name="user/a"))
        selection = self._selection([])
        metrics = compute_overview_metrics(df, self._site_payload(), selection, self._redundancy())
        assert metrics["portfolio_quality_score"] == 0.0

    def test_redundancy_counts_forwarded(self) -> None:
        df = _df(_row("a", 70.0))
        redundancy = {"overlap_clusters": [{}], "overlap_pairs": [{}, {}]}
        metrics = compute_overview_metrics(
            df, self._site_payload(), self._selection([]), redundancy
        )
        assert metrics["redundancy_clusters"] == 1
        assert metrics["redundancy_pairs"] == 2

    def test_manager_summary_forwarded(self) -> None:
        df = _df(_row("a", 70.0))
        metrics = compute_overview_metrics(
            df, self._site_payload(), self._selection([]), self._redundancy()
        )
        assert metrics["manager_summary"] == "All good."


# ---------------------------------------------------------------------------
# optimizer.py — repo_penalty_points
# ---------------------------------------------------------------------------


class TestRepoPenaltyPoints:
    def test_extracts_points_by_code(self) -> None:
        score_entry = {
            "penalties": [
                {"code": "README_MISSING", "points": 10.0},
                {"code": "NO_TESTS_DETECTED", "points": 6.0},
            ]
        }
        result = repo_penalty_points(score_entry)
        assert result["README_MISSING"] == 10.0
        assert result["NO_TESTS_DETECTED"] == 6.0

    def test_empty_penalties(self) -> None:
        assert repo_penalty_points({}) == {}
        assert repo_penalty_points({"penalties": []}) == {}

    def test_accumulates_duplicate_codes(self) -> None:
        score_entry = {
            "penalties": [
                {"code": "README_MISSING", "points": 5.0},
                {"code": "README_MISSING", "points": 3.0},
            ]
        }
        result = repo_penalty_points(score_entry)
        assert result["README_MISSING"] == pytest.approx(8.0)

    def test_skips_empty_code(self) -> None:
        score_entry = {"penalties": [{"code": "", "points": 5.0}]}
        assert repo_penalty_points(score_entry) == {}


# ---------------------------------------------------------------------------
# optimizer.py — estimate_action_impact
# ---------------------------------------------------------------------------


class TestEstimateActionImpact:
    def _base_repo_row(self, score: float = 60.0) -> dict[str, Any]:
        return {"global_score": score, "homepage": None, "description": "a repo"}

    def test_known_action_with_matching_penalty(self) -> None:
        score_entry = {"penalties": [{"code": "README_MISSING", "points": 10.0}]}
        result = estimate_action_impact(
            "Write a complete README.",
            review={},
            score_entry=score_entry,
            repo_row=self._base_repo_row(),
        )
        assert result["estimated_score_lift"] == pytest.approx(10.0)
        assert result["effort_units"] > 0
        assert result["roi"] > 0

    def test_lift_capped_at_remaining_room(self) -> None:
        score_entry = {"penalties": [{"code": "README_MISSING", "points": 50.0}]}
        result = estimate_action_impact(
            "Write a complete README.",
            review={},
            score_entry=score_entry,
            repo_row=self._base_repo_row(score=95.0),
        )
        assert result["estimated_score_lift"] <= 5.0

    def test_homepage_fallback_when_missing(self) -> None:
        result = estimate_action_impact(
            "Expose a demo or homepage link when relevant.",
            review={},
            score_entry={},
            repo_row={"global_score": 70.0, "homepage": None, "description": "a repo"},
        )
        assert result["estimated_score_lift"] > 0

    def test_homepage_no_lift_when_present(self) -> None:
        result = estimate_action_impact(
            "Expose a demo or homepage link when relevant.",
            review={},
            score_entry={},
            repo_row={
                "global_score": 70.0,
                "homepage": "https://demo.example.com",
                "description": "a repo",
            },
        )
        assert result["estimated_score_lift"] == 0.0

    def test_unknown_action_uses_fallback(self) -> None:
        result = estimate_action_impact(
            "Some completely unknown action.",
            review={},
            score_entry={},
            repo_row=self._base_repo_row(),
        )
        assert result["category"] == "general"
        assert result["effort_units"] > 0

    def test_roi_is_lift_over_effort(self) -> None:
        score_entry = {"penalties": [{"code": "NO_TESTS_DETECTED", "points": 6.0}]}
        result = estimate_action_impact(
            "Build a core automated test suite.",
            review={},
            score_entry=score_entry,
            repo_row=self._base_repo_row(),
        )
        expected_roi = round(result["estimated_score_lift"] / result["effort_units"], 2)
        assert result["roi"] == pytest.approx(expected_roi)


# ---------------------------------------------------------------------------
# optimizer.py — derive_repo_optimizer_fields
# ---------------------------------------------------------------------------


class TestDeriveRepoOptimizerFields:
    def test_empty_actions_returns_zero_recoverable(self) -> None:
        result = derive_repo_optimizer_fields(
            review={"priority_actions": []},
            score_entry={},
            repo_row={"global_score": 60.0, "homepage": None, "description": "a"},
        )
        assert result["estimated_recoverable_points"] == 0.0
        assert result["top_opportunity"] is None

    def test_opportunities_sorted_by_roi(self) -> None:
        score_entry = {
            "penalties": [
                {"code": "README_MISSING", "points": 10.0},
                {"code": "PYCACHE_COMMITTED", "points": 3.0},
            ]
        }
        review = {
            "priority_actions": [
                {"text": "Write a complete README.", "priority": "high"},
                {"text": "Delete committed __pycache__ directories.", "priority": "high"},
            ]
        }
        result = derive_repo_optimizer_fields(
            review=review,
            score_entry=score_entry,
            repo_row={"global_score": 60.0, "homepage": None, "description": "a"},
        )
        rois = [o["roi"] for o in result["opportunities"]]
        assert rois == sorted(rois, reverse=True)

    def test_score_ceiling_does_not_exceed_100(self) -> None:
        score_entry = {"penalties": [{"code": "README_MISSING", "points": 999.0}]}
        review = {"priority_actions": [{"text": "Write a complete README.", "priority": "high"}]}
        result = derive_repo_optimizer_fields(
            review=review,
            score_entry=score_entry,
            repo_row={"global_score": 90.0, "homepage": None, "description": "a"},
        )
        assert result["score_ceiling"] <= 100.0


# ---------------------------------------------------------------------------
# optimizer.py — simulate_portfolio
# ---------------------------------------------------------------------------


class TestSimulatePortfolio:
    def test_current_quality_is_mean_of_visible(self) -> None:
        df = _df(
            _row("a", 80.0, group="keep"),
            _row("b", 60.0, group="keep"),
            _row("c", 40.0, group="discard"),
        )
        result = simulate_portfolio(df, [], visible_repo_names=["a", "b"])
        assert result["current_quality"] == pytest.approx(70.0, abs=0.1)

    def test_zero_quality_with_no_visible_repos(self) -> None:
        df = _df(_row("a", 80.0))
        result = simulate_portfolio(df, [], visible_repo_names=[])
        assert result["current_quality"] == 0.0

    def test_quality_after_top3_gte_current(self) -> None:
        df = _df(
            _row("a", 60.0, group="keep"),
            _row("b", 50.0, group="keep"),
        )
        # Inject a fake action that lifts repo a
        fake_action = {
            "action": "Fix tests",
            "roi": 3.0,
            "estimated_total_score_lift": 6.0,
            "repos": [{"repo_name": "a", "estimated_score_lift": 6.0}],
        }
        result = simulate_portfolio(df, [fake_action], visible_repo_names=["a", "b"])
        assert result["quality_after_top_3"] >= result["current_quality"]

    def test_top_actions_list_has_at_most_three(self) -> None:
        df = _df(_row("a", 70.0, group="keep"))
        actions = [
            {
                "action": f"Action {i}",
                "roi": float(i),
                "estimated_total_score_lift": 1.0,
                "repos": [],
            }
            for i in range(10)
        ]
        result = simulate_portfolio(df, actions, visible_repo_names=["a"])
        assert len(result["top_actions"]) <= 3


# ---------------------------------------------------------------------------
# optimizer.py — build_next_actions
# ---------------------------------------------------------------------------


class TestBuildNextActions:
    def test_aggregates_actions_across_repos(self) -> None:
        df = _df(
            _row("a", 60.0),
            _row("b", 55.0),
        )
        # Manually inject optimizer_payload into the df rows
        actions_a = [
            {
                "text": "Write a complete README.",
                "estimated_score_lift": 10.0,
                "effort_units": 2.0,
                "roi": 5.0,
                "matched_penalty_codes": [],
            }
        ]
        actions_b = [
            {
                "text": "Write a complete README.",
                "estimated_score_lift": 8.0,
                "effort_units": 2.0,
                "roi": 4.0,
                "matched_penalty_codes": [],
            }
        ]
        df.at[0, "optimizer_payload"] = actions_a
        df.at[1, "optimizer_payload"] = actions_b

        review_index = {"a": {"priority_actions": []}, "b": {"priority_actions": []}}
        result = build_next_actions(df, review_index)

        readme_actions = [r for r in result if r["action"] == "Write a complete README."]
        assert len(readme_actions) == 1
        assert readme_actions[0]["affected_repo_count"] == 2

    def test_returns_empty_when_no_opportunities(self) -> None:
        df = _df(_row("a", 70.0))
        result = build_next_actions(df, {"a": {"priority_actions": []}})
        assert result == []

    def test_actions_sorted_by_roi(self) -> None:
        df = _df(_row("a", 60.0))
        df.at[0, "optimizer_payload"] = [
            {
                "text": "Low ROI action.",
                "estimated_score_lift": 1.0,
                "effort_units": 3.0,
                "roi": 0.33,
                "matched_penalty_codes": [],
            },
            {
                "text": "High ROI action.",
                "estimated_score_lift": 6.0,
                "effort_units": 1.0,
                "roi": 6.0,
                "matched_penalty_codes": [],
            },
        ]
        review_index = {"a": {"priority_actions": []}}
        result = build_next_actions(df, review_index)
        rois = [r["roi"] for r in result]
        assert rois == sorted(rois, reverse=True)


# ---------------------------------------------------------------------------
# optimizer.py — SEVERITY_ORDER sanity
# ---------------------------------------------------------------------------


def test_severity_order_values() -> None:
    assert SEVERITY_ORDER["high"] > SEVERITY_ORDER["medium"] > SEVERITY_ORDER["low"]


def test_action_impact_rules_completeness() -> None:
    """Every rule must have the required keys."""
    required = {"penalty_codes", "fallback_points", "effort_units", "category"}
    for action, rule in ACTION_IMPACT_RULES.items():
        missing = required - rule.keys()
        assert not missing, f"Rule for '{action}' is missing keys: {missing}"
