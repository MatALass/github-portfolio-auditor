from __future__ import annotations

from tests.golden.conftest import assert_matches_snapshot


def _canonicalize_score(score) -> dict:
    return {
        "repo_full_name": score.repo_full_name,
        "global_score": score.global_score,
        "score_label": score.score_label,
        "confidence": score.confidence,
        "raw_score": score.raw_score,
        "total_penalties": score.total_penalties,
        "breakdown": score.breakdown.model_dump(),
        "penalties": [penalty.model_dump() for penalty in score.penalties],
    }



def test_scoring_matches_golden_snapshot(scored_repositories: list[dict]) -> None:
    actual = [_canonicalize_score(item["score"]) for item in scored_repositories]
    assert_matches_snapshot("scoring_baseline.json", actual)
