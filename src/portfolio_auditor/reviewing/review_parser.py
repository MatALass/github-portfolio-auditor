from __future__ import annotations

"""
reviewing/review_parser.py

Parses a structured LLM JSON response into a RepoReview, validating required
fields and falling back gracefully on partial or malformed output.

Expected JSON shape
-------------------
{
  "executive_summary": "...",
  "recruiter_signal": "...",
  "strengths": [{"text": "...", "priority": "high|medium|low"}],
  "weaknesses": [{"text": "...", "priority": "..."}],
  "blockers": [{"text": "...", "priority": "high"}],
  "quick_wins": [{"text": "...", "priority": "..."}],
  "priority_actions": [{"text": "...", "priority": "..."}],
  "portfolio_decision": "FEATURE_NOW|KEEP_AND_IMPROVE|MERGE_OR_REPOSITION|ARCHIVE_PUBLIC|MAKE_PRIVATE",
  "portfolio_rationale": "..."
}

All keys are optional — missing or null values are silently skipped.
Unknown portfolio_decision values fall back to KEEP_AND_IMPROVE with a warning.
"""

import json
import logging
import re
from typing import Any

from portfolio_auditor.models.portfolio_decision import PortfolioDecision
from portfolio_auditor.models.repo_review import RepoReview

logger = logging.getLogger(__name__)

_VALID_PRIORITIES = {"high", "medium", "low"}
_VALID_DECISIONS = {d.value for d in PortfolioDecision}


class LLMResponseParseError(ValueError):
    """Raised when the raw LLM response cannot be parsed into valid JSON at all."""


def parse_llm_review(
    raw_response: str,
    *,
    repo_name: str,
    repo_full_name: str,
) -> RepoReview:
    """
    Parse a raw LLM response string into a ``RepoReview``.

    Parameters
    ----------
    raw_response:
        Raw text from the LLM. May contain markdown fences (```json ... ```)
        that are stripped before JSON parsing.
    repo_name:
        Repo short name for the resulting ``RepoReview``.
    repo_full_name:
        Full ``owner/repo`` identifier for the resulting ``RepoReview``.

    Returns
    -------
    RepoReview
        Partially or fully populated from the parsed JSON. Fields that are
        missing, null, or invalid are silently skipped.

    Raises
    ------
    LLMResponseParseError
        If the text cannot be decoded as JSON even after stripping fences.
    """
    data = _extract_json(raw_response)

    review = RepoReview(
        repo_name=repo_name,
        repo_full_name=repo_full_name,
    )

    review.executive_summary = _extract_text(data, "executive_summary")
    review.recruiter_signal = _extract_text(data, "recruiter_signal")
    review.portfolio_rationale = _extract_text(data, "portfolio_rationale")

    for item in _extract_bullets(data, "strengths"):
        review.add_strength(item["text"], priority=item.get("priority"))

    for item in _extract_bullets(data, "weaknesses"):
        review.add_weakness(item["text"], priority=item.get("priority"))

    for item in _extract_bullets(data, "blockers"):
        review.add_blocker(item["text"], priority=item.get("priority"))

    for item in _extract_bullets(data, "quick_wins"):
        review.add_quick_win(item["text"], priority=item.get("priority"))

    for item in _extract_bullets(data, "priority_actions"):
        review.add_priority_action(item["text"], priority=item.get("priority"))

    review.portfolio_decision = _extract_decision(data)

    return review


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_json(raw: str) -> dict[str, Any]:
    """Strip markdown fences then JSON-decode. Raises LLMResponseParseError on failure."""
    # Remove ```json ... ``` or ``` ... ``` wrappers
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMResponseParseError(
            f"LLM response is not valid JSON after stripping fences. "
            f"Original error: {exc}. "
            f"First 200 chars of cleaned text: {cleaned[:200]!r}"
        ) from exc

    if not isinstance(parsed, dict):
        raise LLMResponseParseError(
            f"Expected a JSON object at the top level, got {type(parsed).__name__}."
        )
    return parsed


def _extract_text(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _extract_bullets(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """
    Extract a list of bullet dicts from the parsed JSON.

    Accepts both:
    - list of dicts: [{"text": "...", "priority": "high"}, ...]
    - list of strings: ["...", "..."]  (treated as text-only, no priority)
    """
    raw = data.get(key)
    if not isinstance(raw, list):
        return []

    bullets: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            text = item.strip()
            if text:
                bullets.append({"text": text})
        elif isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            priority_raw = str(item.get("priority", "")).strip().lower()
            priority = priority_raw if priority_raw in _VALID_PRIORITIES else None
            bullets.append({"text": text, "priority": priority})

    return bullets


def _extract_decision(data: dict[str, Any]) -> PortfolioDecision:
    raw = data.get("portfolio_decision")
    if not isinstance(raw, str):
        return PortfolioDecision.KEEP_AND_IMPROVE

    candidate = raw.strip().upper()
    if candidate not in _VALID_DECISIONS:
        logger.warning(
            "Unknown portfolio_decision value %r from LLM — falling back to KEEP_AND_IMPROVE",
            raw,
        )
        return PortfolioDecision.KEEP_AND_IMPROVE

    return PortfolioDecision(candidate)
