from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from portfolio_auditor.models.portfolio_decision import PortfolioDecision


class ReviewBullet(BaseModel):
    """
    Small structured review item used in UI and exports.
    """

    text: str = Field(..., min_length=1)
    priority: str | None = None

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("text cannot be empty")
        return text

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip().lower()
        return text or None


class RepoReview(BaseModel):
    """
    Final deterministic or LLM-assisted narrative review for a repository.
    """

    repo_name: str = Field(..., min_length=1)
    repo_full_name: str = Field(..., min_length=1)

    executive_summary: str | None = None
    strengths: list[ReviewBullet] = Field(default_factory=list)
    weaknesses: list[ReviewBullet] = Field(default_factory=list)
    blockers: list[ReviewBullet] = Field(default_factory=list)
    quick_wins: list[ReviewBullet] = Field(default_factory=list)
    priority_actions: list[ReviewBullet] = Field(default_factory=list)

    portfolio_decision: PortfolioDecision = PortfolioDecision.KEEP_AND_IMPROVE
    portfolio_rationale: str | None = None
    recruiter_signal: str | None = None

    @field_validator("repo_name", "repo_full_name", mode="before")
    @classmethod
    def strip_required_strings(cls, value: Any) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("field cannot be empty")
        return text

    @field_validator("executive_summary", "portfolio_rationale", "recruiter_signal", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def add_strength(self, text: str, priority: str | None = None) -> None:
        self.strengths.append(ReviewBullet(text=text, priority=priority))

    def add_weakness(self, text: str, priority: str | None = None) -> None:
        self.weaknesses.append(ReviewBullet(text=text, priority=priority))

    def add_blocker(self, text: str, priority: str | None = None) -> None:
        self.blockers.append(ReviewBullet(text=text, priority=priority))

    def add_quick_win(self, text: str, priority: str | None = None) -> None:
        self.quick_wins.append(ReviewBullet(text=text, priority=priority))

    def add_priority_action(self, text: str, priority: str | None = None) -> None:
        self.priority_actions.append(ReviewBullet(text=text, priority=priority))

    def to_flat_dict(self) -> dict[str, Any]:
        return {
            "repo_name": self.repo_name,
            "repo_full_name": self.repo_full_name,
            "executive_summary": self.executive_summary,
            "portfolio_decision": self.portfolio_decision.value,
            "portfolio_rationale": self.portfolio_rationale,
            "recruiter_signal": self.recruiter_signal,
            "strengths_count": len(self.strengths),
            "weaknesses_count": len(self.weaknesses),
            "blockers_count": len(self.blockers),
            "quick_wins_count": len(self.quick_wins),
            "priority_actions_count": len(self.priority_actions),
            "strengths": " | ".join(item.text for item in self.strengths),
            "weaknesses": " | ".join(item.text for item in self.weaknesses),
            "blockers": " | ".join(item.text for item in self.blockers),
            "quick_wins": " | ".join(item.text for item in self.quick_wins),
            "priority_actions": " | ".join(item.text for item in self.priority_actions),
        }