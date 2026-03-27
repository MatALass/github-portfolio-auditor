from __future__ import annotations

from tests.golden.conftest import assert_matches_snapshot


def test_selection_matches_golden_snapshot(selection_result) -> None:
    actual = {
        "featured_repos": [repo.repo_full_name for repo in selection_result.featured_repos],
        "keep_visible_but_improve": [
            repo.repo_full_name for repo in selection_result.keep_visible_but_improve
        ],
        "improvement_backlog": [repo.repo_full_name for repo in selection_result.improvement_backlog],
        "archive_candidates": [repo.repo_full_name for repo in selection_result.archive_candidates],
        "private_candidates": [repo.repo_full_name for repo in selection_result.private_candidates],
        "redundancy_candidates": [repo.repo_full_name for repo in selection_result.redundancy_candidates],
        "manager_summary": selection_result.manager_summary,
    }
    assert_matches_snapshot("selection_baseline.json", actual)
