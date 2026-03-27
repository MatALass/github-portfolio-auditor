from __future__ import annotations

from tests.golden.conftest import assert_matches_snapshot


def _canonicalize_ranked_repo(repo) -> dict:
    return {
        "rank": repo.rank,
        "repo_full_name": repo.repo_full_name,
        "global_score": repo.global_score,
        "portfolio_decision": repo.portfolio_decision,
        "confidence": repo.confidence,
        "blockers_count": repo.blockers_count,
        "priority_actions_count": repo.priority_actions_count,
        "redundancy_status": repo.redundancy_status,
        "strongest_overlap_score": repo.strongest_overlap_score,
        "representative_repo_full_name": repo.representative_repo_full_name,
    }



def test_ranking_matches_golden_snapshot(ranking_summary) -> None:
    redundancy = ranking_summary.redundancy_analysis.to_dict()
    actual = {
        "ranked_repos": [_canonicalize_ranked_repo(repo) for repo in ranking_summary.ranked_repos],
        "feature_now": [repo.repo_full_name for repo in ranking_summary.feature_now],
        "keep_and_improve": [repo.repo_full_name for repo in ranking_summary.keep_and_improve],
        "merge_or_reposition": [repo.repo_full_name for repo in ranking_summary.merge_or_reposition],
        "archive_public": [repo.repo_full_name for repo in ranking_summary.archive_public],
        "make_private": [repo.repo_full_name for repo in ranking_summary.make_private],
        "highest_priority_improvements": [
            repo.repo_full_name for repo in ranking_summary.highest_priority_improvements
        ],
        "overlap_pairs": redundancy["overlap_pairs"],
        "overlap_clusters": redundancy["overlap_clusters"],
        "repo_statuses": redundancy["repo_statuses"],
    }
    assert_matches_snapshot("ranking_baseline.json", actual)
