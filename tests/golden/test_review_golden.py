from __future__ import annotations

from tests.golden.conftest import assert_matches_snapshot


def _canonicalize_review(review) -> dict:
    return {
        "repo_full_name": review.repo_full_name,
        "executive_summary": review.executive_summary,
        "recruiter_signal": review.recruiter_signal,
        "portfolio_decision": review.portfolio_decision.value,
        "portfolio_rationale": review.portfolio_rationale,
        "strengths": [item.model_dump() for item in review.strengths],
        "weaknesses": [item.model_dump() for item in review.weaknesses],
        "blockers": [item.model_dump() for item in review.blockers],
        "quick_wins": [item.model_dump() for item in review.quick_wins],
        "priority_actions": [item.model_dump() for item in review.priority_actions],
    }



def test_review_matches_golden_snapshot(reviewed_repositories: list[dict]) -> None:
    actual = [_canonicalize_review(item["review"]) for item in reviewed_repositories]
    assert_matches_snapshot("review_baseline.json", actual)
