from __future__ import annotations

from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_review import RepoReview
from portfolio_auditor.models.repo_scan import RepoScanResult
from portfolio_auditor.models.repo_score import RepoScore
from portfolio_auditor.reviewing.deterministic_review import DeterministicReviewer

reviewer = DeterministicReviewer()


def review_repo_with_llm(
    repo: RepoMetadata,
    scan: RepoScanResult,
    score: RepoScore,
) -> RepoReview:
    """
    Temporary deterministic fallback.
    A future LLM layer should wrap this result rather than replace it.
    """
    return reviewer.review(repo, scan, score)