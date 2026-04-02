"""
tests/unit/test_review_parser.py

Unit tests for the LLM review response parser.
"""

from __future__ import annotations

import json

import pytest

from portfolio_auditor.models.portfolio_decision import PortfolioDecision
from portfolio_auditor.reviewing.review_parser import LLMResponseParseError, parse_llm_review


def _build_valid_payload(**overrides) -> str:
    base = {
        "executive_summary": "Strong repo with good structure.",
        "recruiter_signal": "Positive signal for senior roles.",
        "portfolio_rationale": "Worth featuring.",
        "strengths": [{"text": "Well-documented", "priority": "high"}],
        "weaknesses": [{"text": "No integration tests", "priority": "medium"}],
        "blockers": [],
        "quick_wins": [{"text": "Add a demo link", "priority": "low"}],
        "priority_actions": [{"text": "Write a complete README.", "priority": "high"}],
        "portfolio_decision": "KEEP_AND_IMPROVE",
    }
    base.update(overrides)
    return json.dumps(base)


class TestParseValidResponse:
    def test_basic_fields_parsed(self) -> None:
        raw = _build_valid_payload()
        review = parse_llm_review(raw, repo_name="my-repo", repo_full_name="user/my-repo")

        assert review.repo_name == "my-repo"
        assert review.repo_full_name == "user/my-repo"
        assert review.executive_summary == "Strong repo with good structure."
        assert review.recruiter_signal == "Positive signal for senior roles."
        assert review.portfolio_rationale == "Worth featuring."

    def test_strengths_parsed(self) -> None:
        raw = _build_valid_payload(strengths=[{"text": "Excellent tests", "priority": "high"}])
        review = parse_llm_review(raw, repo_name="r", repo_full_name="u/r")

        assert len(review.strengths) == 1
        assert review.strengths[0].text == "Excellent tests"
        assert review.strengths[0].priority == "high"

    def test_weaknesses_parsed(self) -> None:
        raw = _build_valid_payload(weaknesses=[{"text": "No CI", "priority": "medium"}])
        review = parse_llm_review(raw, repo_name="r", repo_full_name="u/r")

        assert len(review.weaknesses) == 1
        assert review.weaknesses[0].text == "No CI"

    def test_blockers_parsed(self) -> None:
        raw = _build_valid_payload(blockers=[{"text": "Committed venv", "priority": "high"}])
        review = parse_llm_review(raw, repo_name="r", repo_full_name="u/r")

        assert len(review.blockers) == 1

    def test_portfolio_decision_parsed(self) -> None:
        for decision in [
            "FEATURE_NOW",
            "KEEP_AND_IMPROVE",
            "MERGE_OR_REPOSITION",
            "ARCHIVE_PUBLIC",
            "MAKE_PRIVATE",
        ]:
            raw = _build_valid_payload(portfolio_decision=decision)
            review = parse_llm_review(raw, repo_name="r", repo_full_name="u/r")
            assert review.portfolio_decision == PortfolioDecision(decision)

    def test_markdown_fences_stripped(self) -> None:
        payload = _build_valid_payload()
        fenced = f"```json\n{payload}\n```"
        review = parse_llm_review(fenced, repo_name="r", repo_full_name="u/r")

        assert review.executive_summary is not None

    def test_markdown_fences_without_lang_stripped(self) -> None:
        payload = _build_valid_payload()
        fenced = f"```\n{payload}\n```"
        review = parse_llm_review(fenced, repo_name="r", repo_full_name="u/r")

        assert review.executive_summary is not None


class TestParseInvalidResponse:
    def test_invalid_json_raises(self) -> None:
        with pytest.raises(LLMResponseParseError):
            parse_llm_review("not-json", repo_name="r", repo_full_name="u/r")

    def test_missing_required_field_falls_back_to_keep_and_improve(self) -> None:
        raw = json.dumps(
            {
                "executive_summary": "ok",
                "recruiter_signal": "ok",
                "portfolio_rationale": "ok",
                "strengths": [],
                "weaknesses": [],
                "blockers": [],
                "quick_wins": [],
                "priority_actions": [],
            }
        )
        review = parse_llm_review(raw, repo_name="r", repo_full_name="u/r")

        assert review.portfolio_decision == PortfolioDecision.KEEP_AND_IMPROVE


    def test_invalid_decision_falls_back_to_keep_and_improve(self) -> None:
        raw = _build_valid_payload(portfolio_decision="NOT_A_REAL_DECISION")
        review = parse_llm_review(raw, repo_name="r", repo_full_name="u/r")

        assert review.portfolio_decision == PortfolioDecision.KEEP_AND_IMPROVE