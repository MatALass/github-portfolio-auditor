from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScoreWeights:
    """
    Weight allocation for the portfolio score.
    Total must equal 100.
    """

    architecture_structure: float = 20.0
    documentation_delivery: float = 20.0
    testing_reliability: float = 15.0
    technical_depth: float = 15.0
    portfolio_relevance: float = 20.0
    maintainability_cleanliness: float = 10.0

    @property
    def total(self) -> float:
        return (
            self.architecture_structure
            + self.documentation_delivery
            + self.testing_reliability
            + self.technical_depth
            + self.portfolio_relevance
            + self.maintainability_cleanliness
        )

    def validate(self) -> None:
        if round(self.total, 5) != 100.0:
            raise ValueError(f"ScoreWeights total must be 100. Got {self.total}.")