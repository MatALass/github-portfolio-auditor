from __future__ import annotations

"""
tests/unit/test_review_parser.py

Unit tests for the LLM review response parser.
"""

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
        for decision in ["FEATURE_NOW", "KEEP_AND_IMPROVE", "MERGE_OR_REPOSITION", "ARCHIVE_PUBLIC", "MAKE_PRIVATE"]:
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

        assert review.portfolio_decision == PortfolioDecision.KEEP_AND_IMPROVE

    def test_string_bullets_accepted(self) -> None:
        raw = _build_valid_payload(strengths=["Great tests", "Nice structure"])
        review = parse_llm_review(raw, repo_name="r", repo_full_name="u/r")

        assert len(review.strengths) == 2
        assert review.strengths[0].text == "Great tests"
        assert review.strengths[0].priority is None


class TestPartialOrMissingFields:
    def test_missing_executive_summary_is_none(self) -> None:
        payload = {
            "portfolio_decision": "KEEP_AND_IMPROVE",
            "strengths": [],
        }
        review = parse_llm_review(json.dumps(payload), repo_name="r", repo_full_name="u/r")

        assert review.executive_summary is None

    def test_missing_bullets_result_in_empty_lists(self) -> None:
        payload = {"portfolio_decision": "FEATURE_NOW"}
        review = parse_llm_review(json.dumps(payload), repo_name="r", repo_full_name="u/r")

        assert review.strengths == []
        assert review.weaknesses == []
        assert review.blockers == []
        assert review.quick_wins == []
        assert review.priority_actions == []

    def test_unknown_priority_coerced_to_none(self) -> None:
        raw = _build_valid_payload(strengths=[{"text": "Great tests", "priority": "critical"}])
        review = parse_llm_review(raw, repo_name="r", repo_full_name="u/r")

        assert review.strengths[0].priority is None

    def test_empty_text_bullets_skipped(self) -> None:
        raw = _build_valid_payload(
            strengths=[{"text": "  ", "priority": "high"}, {"text": "Good docs", "priority": "medium"}]
        )
        review = parse_llm_review(raw, repo_name="r", repo_full_name="u/r")

        assert len(review.strengths) == 1
        assert review.strengths[0].text == "Good docs"

    def test_unknown_decision_falls_back_to_keep_and_improve(self) -> None:
        raw = _build_valid_payload(portfolio_decision="INVALID_VALUE")
        review = parse_llm_review(raw, repo_name="r", repo_full_name="u/r")

        assert review.portfolio_decision == PortfolioDecision.KEEP_AND_IMPROVE

    def test_null_decision_falls_back(self) -> None:
        raw = _build_valid_payload(portfolio_decision=None)
        review = parse_llm_review(raw, repo_name="r", repo_full_name="u/r")

        assert review.portfolio_decision == PortfolioDecision.KEEP_AND_IMPROVE


class TestInvalidInput:
    def test_non_json_raises(self) -> None:
        with pytest.raises(LLMResponseParseError):
            parse_llm_review("This is plain text, not JSON.", repo_name="r", repo_full_name="u/r")

    def test_json_array_raises(self) -> None:
        with pytest.raises(LLMResponseParseError):
            parse_llm_review("[1, 2, 3]", repo_name="r", repo_full_name="u/r")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(LLMResponseParseError):
            parse_llm_review("", repo_name="r", repo_full_name="u/r")

    def test_json_scalar_raises(self) -> None:
        with pytest.raises(LLMResponseParseError):
            parse_llm_review('"just a string"', repo_name="r", repo_full_name="u/r")
