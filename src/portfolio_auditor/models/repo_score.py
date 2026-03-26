from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ScoreBreakdown(BaseModel):
    """
    Weighted sub-scores on a 100-point scale.
    """

    architecture_structure: float = Field(default=0.0, ge=0.0, le=20.0)
    documentation_delivery: float = Field(default=0.0, ge=0.0, le=20.0)
    testing_reliability: float = Field(default=0.0, ge=0.0, le=15.0)
    technical_depth: float = Field(default=0.0, ge=0.0, le=15.0)
    portfolio_relevance: float = Field(default=0.0, ge=0.0, le=20.0)
    maintainability_cleanliness: float = Field(default=0.0, ge=0.0, le=10.0)

    @property
    def total_before_penalties(self) -> float:
        return (
            self.architecture_structure
            + self.documentation_delivery
            + self.testing_reliability
            + self.technical_depth
            + self.portfolio_relevance
            + self.maintainability_cleanliness
        )


class PenaltyItem(BaseModel):
    """
    Explicit penalty with a traceable reason.
    """

    code: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    points: float = Field(..., ge=0.0)
    reason: str = Field(..., min_length=1)

    @field_validator("code", "label", "reason", mode="before")
    @classmethod
    def strip_required_strings(cls, value: Any) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("field cannot be empty")
        return text


class ScoreExplanationItem(BaseModel):
    """
    Human-readable explanation for how a score was assigned.
    """

    category: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    supporting_points: list[str] = Field(default_factory=list)

    @field_validator("category", "summary", mode="before")
    @classmethod
    def strip_required_strings(cls, value: Any) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("field cannot be empty")
        return text


class RepoScore(BaseModel):
    """
    Final score artifact used by ranking, exports, and dashboard rendering.
    """

    repo_name: str = Field(..., min_length=1)
    repo_full_name: str = Field(..., min_length=1)
    global_score: float = Field(default=0.0, ge=0.0, le=100.0)
    breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    penalties: list[PenaltyItem] = Field(default_factory=list)
    explanations: list[ScoreExplanationItem] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("repo_name", "repo_full_name", mode="before")
    @classmethod
    def strip_required_strings(cls, value: Any) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("field cannot be empty")
        return text

    def recompute_global_score(self) -> None:
        raw_total = self.breakdown.total_before_penalties
        penalty_total = sum(item.points for item in self.penalties)
        self.global_score = max(0.0, min(100.0, round(raw_total - penalty_total, 2)))

    @property
    def raw_score(self) -> float:
        return round(self.breakdown.total_before_penalties, 2)

    @property
    def total_penalties(self) -> float:
        return round(sum(item.points for item in self.penalties), 2)

    @property
    def score_label(self) -> str:
        score = self.global_score
        if score >= 85:
            return "excellent"
        if score >= 75:
            return "strong"
        if score >= 60:
            return "good"
        if score >= 45:
            return "fair"
        return "weak"

    def to_flat_dict(self) -> dict[str, Any]:
        return {
            "repo_name": self.repo_name,
            "repo_full_name": self.repo_full_name,
            "global_score": self.global_score,
            "score_label": self.score_label,
            "confidence": self.confidence,
            "raw_score": self.raw_score,
            "total_penalties": self.total_penalties,
            "architecture_structure": self.breakdown.architecture_structure,
            "documentation_delivery": self.breakdown.documentation_delivery,
            "testing_reliability": self.breakdown.testing_reliability,
            "technical_depth": self.breakdown.technical_depth,
            "portfolio_relevance": self.breakdown.portfolio_relevance,
            "maintainability_cleanliness": self.breakdown.maintainability_cleanliness,
            "penalty_count": len(self.penalties),
        }