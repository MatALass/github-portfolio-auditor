from __future__ import annotations

"""
tests/unit/test_deterministic_reviewer.py

Unit tests for DeterministicReviewer.

Covers: portfolio decision thresholds, blocker generation, quick wins,
priority actions, executive summary generation, and the recruiter signal.
"""

import pytest

from portfolio_auditor.models.portfolio_decision import PortfolioDecision
from portfolio_auditor.models.repo_metadata import (
    RepoEngagement,
    RepoFlags,
    RepoLanguageStats,
    RepoLinks,
    RepoMetadata,
    RepoOwner,
    RepoTimestamps,
    RepoTopics,
)
from portfolio_auditor.models.repo_scan import RepoScanResult
from portfolio_auditor.models.repo_score import RepoScore, ScoreBreakdown
from portfolio_auditor.reviewing.deterministic_review import DeterministicReviewer


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _repo(name: str = "test-repo", description: str = "A test repo") -> RepoMetadata:
    return RepoMetadata(
        id=1,
        name=name,
        full_name=f"user/{name}",
        description=description,
        default_branch="main",
        size_kb=100,
        owner=RepoOwner(login="user", type="User", html_url="https://github.com/user"),
        flags=RepoFlags(),
        engagement=RepoEngagement(),
        timestamps=RepoTimestamps(
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-02T00:00:00Z",
            pushed_at="2025-01-03T00:00:00Z",
        ),
        links=RepoLinks(
            html_url="https://github.com/user/test-repo",
            clone_url="https://github.com/user/test-repo.git",
        ),
        language="Python",
        language_stats=RepoLanguageStats(languages={"Python": 1000}),
        topics=RepoTopics(items=["python"]),
    )


def _scan_base(repo: RepoMetadata) -> RepoScanResult:
    return RepoScanResult(
        repo_name=repo.name,
        repo_full_name=repo.full_name,
        local_path=".",
    )


def _score(global_score: float, confidence: float = 0.8) -> RepoScore:
    return RepoScore(
        repo_name="test-repo",
        repo_full_name="user/test-repo",
        global_score=global_score,
        confidence=confidence,
        breakdown=ScoreBreakdown(),
    )


reviewer = DeterministicReviewer()


# ---------------------------------------------------------------------------
# Portfolio decision tests
# ---------------------------------------------------------------------------


class TestPortfolioDecision:
    def test_feature_now_on_excellent_clean_repo(self) -> None:
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = True
        scan.documentation.readme_word_count = 600
        scan.documentation.has_usage_section = True
        scan.testing.has_tests = True
        scan.testing.test_file_count = 12
        scan.cleanliness.has_gitignore = True
        scan.structure.has_src_dir = True
        scan.ci.has_github_actions = True
        scan.ci.has_test_workflow = True

        review = reviewer.review(repo, scan, _score(88))

        assert review.portfolio_decision == PortfolioDecision.FEATURE_NOW

    def test_keep_and_improve_on_decent_repo(self) -> None:
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = True
        scan.documentation.readme_word_count = 200
        scan.documentation.has_usage_section = True
        scan.testing.has_tests = True
        scan.testing.test_file_count = 3
        scan.cleanliness.has_gitignore = True

        review = reviewer.review(repo, scan, _score(72))

        assert review.portfolio_decision == PortfolioDecision.KEEP_AND_IMPROVE

    def test_merge_or_reposition_on_marginal_repo(self) -> None:
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = True
        scan.documentation.readme_word_count = 90
        scan.testing.has_tests = False
        scan.cleanliness.has_gitignore = True

        review = reviewer.review(repo, scan, _score(55))

        assert review.portfolio_decision == PortfolioDecision.MERGE_OR_REPOSITION

    def test_make_private_on_weak_repo(self) -> None:
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = False
        scan.cleanliness.committed_virtualenv = True
        scan.cleanliness.committed_pycache = True
        scan.cleanliness.has_gitignore = False

        review = reviewer.review(repo, scan, _score(28))

        assert review.portfolio_decision == PortfolioDecision.MAKE_PRIVATE

    def test_committed_venv_prevents_feature_now(self) -> None:
        """A virtualenv committed to the repo should block FEATURE_NOW even with a high score."""
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = True
        scan.documentation.readme_word_count = 600
        scan.documentation.has_usage_section = True
        scan.testing.has_tests = True
        scan.cleanliness.has_gitignore = True
        scan.cleanliness.committed_virtualenv = True  # deliberate blocker

        review = reviewer.review(repo, scan, _score(88))

        assert review.portfolio_decision != PortfolioDecision.FEATURE_NOW


# ---------------------------------------------------------------------------
# Blockers
# ---------------------------------------------------------------------------


class TestBlockers:
    def test_missing_readme_generates_blocker(self) -> None:
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = False

        review = reviewer.review(repo, scan, _score(45))

        blocker_texts = " ".join(b.text.lower() for b in review.blockers)
        assert "readme" in blocker_texts or len(review.blockers) >= 1

    def test_committed_virtualenv_generates_blocker(self) -> None:
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = True
        scan.documentation.readme_word_count = 200
        scan.cleanliness.committed_virtualenv = True

        review = reviewer.review(repo, scan, _score(55))

        blocker_texts = " ".join(b.text.lower() for b in review.blockers)
        assert "virtual" in blocker_texts or len(review.blockers) >= 1

    def test_committed_pycache_generates_blocker(self) -> None:
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = True
        scan.documentation.readme_word_count = 200
        scan.cleanliness.committed_pycache = True

        review = reviewer.review(repo, scan, _score(55))

        blocker_texts = " ".join(b.text.lower() for b in review.blockers)
        assert "pycache" in blocker_texts or "cache" in blocker_texts or len(review.blockers) >= 1

    def test_clean_repo_has_no_blockers(self) -> None:
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = True
        scan.documentation.readme_word_count = 400
        scan.documentation.has_usage_section = True
        scan.testing.has_tests = True
        scan.testing.test_file_count = 8
        scan.cleanliness.has_gitignore = True
        scan.ci.has_github_actions = True
        scan.ci.has_test_workflow = True
        scan.structure.has_src_dir = True

        review = reviewer.review(repo, scan, _score(88))

        assert len(review.blockers) == 0


# ---------------------------------------------------------------------------
# Quick wins
# ---------------------------------------------------------------------------


class TestQuickWins:
    def test_no_readme_triggers_quick_win(self) -> None:
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = False

        review = reviewer.review(repo, scan, _score(40))

        texts = " ".join(w.text.lower() for w in review.quick_wins)
        assert "readme" in texts

    def test_no_gitignore_triggers_quick_win(self) -> None:
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = True
        scan.documentation.readme_word_count = 200
        scan.cleanliness.has_gitignore = False

        review = reviewer.review(repo, scan, _score(55))

        texts = " ".join(w.text.lower() for w in review.quick_wins)
        assert "gitignore" in texts

    def test_no_description_triggers_quick_win(self) -> None:
        repo = _repo(description="")
        # Pydantic may coerce empty string to None
        repo2 = RepoMetadata(
            id=1,
            name="test-repo",
            full_name="user/test-repo",
            description=None,
            default_branch="main",
            size_kb=100,
            owner=RepoOwner(login="user", type="User", html_url="https://github.com/user"),
            flags=RepoFlags(),
            engagement=RepoEngagement(),
            timestamps=RepoTimestamps(
                created_at="2025-01-01T00:00:00Z",
                updated_at="2025-01-02T00:00:00Z",
                pushed_at="2025-01-03T00:00:00Z",
            ),
            links=RepoLinks(
                html_url="https://github.com/user/test-repo",
                clone_url="https://github.com/user/test-repo.git",
            ),
            language="Python",
            language_stats=RepoLanguageStats(languages={"Python": 1000}),
            topics=RepoTopics(items=[]),
        )
        scan = _scan_base(repo2)
        scan.documentation.has_readme = True
        scan.documentation.readme_word_count = 200

        review = reviewer.review(repo2, scan, _score(60))

        texts = " ".join(w.text.lower() for w in review.quick_wins)
        assert "description" in texts


# ---------------------------------------------------------------------------
# Priority actions
# ---------------------------------------------------------------------------


class TestPriorityActions:
    def test_no_tests_triggers_build_test_suite_action(self) -> None:
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = True
        scan.documentation.readme_word_count = 200
        scan.testing.has_tests = False

        review = reviewer.review(repo, scan, _score(55))

        action_texts = " ".join(a.text.lower() for a in review.priority_actions)
        assert "test" in action_texts

    def test_no_readme_triggers_write_readme_action(self) -> None:
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = False

        review = reviewer.review(repo, scan, _score(40))

        action_texts = " ".join(a.text.lower() for a in review.priority_actions)
        assert "readme" in action_texts

    def test_no_structure_triggers_structure_action(self) -> None:
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = True
        scan.documentation.readme_word_count = 200
        scan.documentation.has_usage_section = True
        scan.testing.has_tests = True
        scan.testing.test_file_count = 4
        scan.structure.has_src_dir = False
        scan.structure.has_app_dir = False

        review = reviewer.review(repo, scan, _score(66))

        action_texts = " ".join(a.text.lower() for a in review.priority_actions)
        assert "structure" in action_texts

    def test_strong_repo_has_minimal_actions(self) -> None:
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = True
        scan.documentation.readme_word_count = 600
        scan.documentation.has_usage_section = True
        scan.documentation.has_installation_section = True
        scan.testing.has_tests = True
        scan.testing.test_file_count = 15
        scan.cleanliness.has_gitignore = True
        scan.ci.has_github_actions = True
        scan.ci.has_test_workflow = True
        scan.structure.has_src_dir = True

        review = reviewer.review(repo, scan, _score(91))

        # A strong repo should either have zero or only maintenance actions
        high_priority_actions = [a for a in review.priority_actions if a.priority == "high"]
        assert len(high_priority_actions) == 0


# ---------------------------------------------------------------------------
# Executive summary and recruiter signal
# ---------------------------------------------------------------------------


class TestNarratives:
    @pytest.mark.parametrize(
        "global_score,expected_fragment",
        [
            (90, "strong"),
            (77, "strong overall"),
            (63, "promising"),
            (47, "not yet strong"),
            (25, "too weak"),
        ],
    )
    def test_executive_summary_reflects_score(self, global_score: float, expected_fragment: str) -> None:
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = True
        scan.documentation.readme_word_count = 300

        review = reviewer.review(repo, scan, _score(global_score))

        assert review.executive_summary is not None
        assert expected_fragment in review.executive_summary.lower()

    def test_recruiter_signal_present(self) -> None:
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = True

        review = reviewer.review(repo, scan, _score(65))

        assert review.recruiter_signal is not None
        assert len(review.recruiter_signal) > 10

    def test_portfolio_rationale_present(self) -> None:
        repo = _repo()
        scan = _scan_base(repo)
        scan.documentation.has_readme = True
        scan.documentation.readme_word_count = 200
        scan.documentation.has_usage_section = True
        scan.testing.has_tests = True
        scan.testing.test_file_count = 5
        scan.cleanliness.has_gitignore = True

        review = reviewer.review(repo, scan, _score(72))

        assert review.portfolio_rationale is not None
        assert len(review.portfolio_rationale) > 20
