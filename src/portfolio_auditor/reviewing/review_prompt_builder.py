from __future__ import annotations

from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_scan import RepoScanResult
from portfolio_auditor.models.repo_score import RepoScore


def build_review_prompt(repo: RepoMetadata, scan: RepoScanResult, score: RepoScore) -> str:
    language = repo.language or repo.language_stats.primary_language or "unknown"
    issues = [issue.code for issue in scan.issues]
    explanations = [item.summary for item in score.explanations]

    return (
        f"Review repository {repo.full_name}. "
        f"Score: {score.global_score}/100 ({score.score_label}). "
        f"Primary language: {language}. "
        f"Issue codes: {issues}. "
        f"Score explanations: {explanations}."
    )