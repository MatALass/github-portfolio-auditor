from __future__ import annotations

from portfolio_auditor.scoring.policy_loader import load_scoring_policy


def test_load_default_scoring_policy() -> None:
    policy = load_scoring_policy()

    assert policy.version == "v1"
    assert policy.weights.total == 100.0
    assert policy.review_thresholds.feature_now_min_score == 85.0
    assert policy.selection.max_featured_repositories == 8
    assert policy.penalty_value("README_MISSING") == 10.0