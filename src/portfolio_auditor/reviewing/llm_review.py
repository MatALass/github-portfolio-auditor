from __future__ import annotations

import logging
import os

from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_review import RepoReview
from portfolio_auditor.models.repo_scan import RepoScanResult
from portfolio_auditor.models.repo_score import RepoScore
from portfolio_auditor.reviewing.deterministic_review import DeterministicReviewer

logger = logging.getLogger(__name__)


class LLMReviewNotImplemented(NotImplementedError):
    """
    Raised when LLM review is explicitly requested but no backend is configured.

    To implement LLM-enhanced review, override ``review_repo_with_llm`` or set
    the ``PORTFOLIO_LLM_REVIEW_ENABLED`` environment variable to ``"false"``
    (default) to keep the deterministic fallback without raising.
    """


def review_repo_with_llm(
    repo: RepoMetadata,
    scan: RepoScanResult,
    score: RepoScore,
) -> RepoReview:
    """
    Entry point for LLM-enhanced review.

    Current state: **not yet implemented**.

    Behaviour is controlled by the ``PORTFOLIO_LLM_REVIEW_ENABLED`` environment
    variable:

    - ``"false"`` (default) — silently falls back to the deterministic reviewer
      and logs a DEBUG message. Safe to call in production without any LLM setup.
    - ``"true"`` — raises ``LLMReviewNotImplemented`` to make it explicit that the
      caller expected a real LLM integration that does not exist yet.

    When implementing:
    - Build the prompt via ``review_prompt_builder.build_prompt(repo, scan, score)``
    - Call the LLM API of your choice
    - Parse the structured response via ``review_parser.parse(raw_response)``
    - Merge or annotate the deterministic review rather than replacing it entirely
    """
    llm_enabled = os.getenv("PORTFOLIO_LLM_REVIEW_ENABLED", "false").strip().lower()

    if llm_enabled == "true":
        raise LLMReviewNotImplemented(
            f"LLM review was explicitly enabled (PORTFOLIO_LLM_REVIEW_ENABLED=true) "
            f"for repo '{repo.full_name}', but no LLM backend has been implemented. "
            "Set PORTFOLIO_LLM_REVIEW_ENABLED=false to use the deterministic fallback, "
            "or implement an LLM integration in this function."
        )

    logger.debug(
        "LLM review not yet implemented — falling back to deterministic reviewer for %s",
        repo.full_name,
    )
    return DeterministicReviewer().review(repo, scan, score)
