from __future__ import annotations

from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_scan import RepoScanResult
from portfolio_auditor.models.repo_score import RepoScore, ScoreBreakdown
from portfolio_auditor.scoring.explainability import ScoreExplainabilityBuilder
from portfolio_auditor.scoring.rules import ScoringRules
from portfolio_auditor.scoring.weighting import ScoreWeights


class ScoringEngine:
    """
    Deterministic portfolio scoring engine.
    """

    def __init__(self, weights: ScoreWeights | None = None) -> None:
        self.weights = weights or ScoreWeights()
        self.weights.validate()

    def score(self, repo: RepoMetadata, scan: RepoScanResult) -> RepoScore:
        components = ScoringRules.compute_components(repo, scan)

        breakdown = ScoreBreakdown(
            architecture_structure=round(
                components.architecture_structure_ratio * self.weights.architecture_structure, 2
            ),
            documentation_delivery=round(
                components.documentation_delivery_ratio * self.weights.documentation_delivery, 2
            ),
            testing_reliability=round(
                components.testing_reliability_ratio * self.weights.testing_reliability, 2
            ),
            technical_depth=round(
                components.technical_depth_ratio * self.weights.technical_depth, 2
            ),
            portfolio_relevance=round(
                components.portfolio_relevance_ratio * self.weights.portfolio_relevance, 2
            ),
            maintainability_cleanliness=round(
                components.maintainability_cleanliness_ratio * self.weights.maintainability_cleanliness,
                2,
            ),
        )

        penalties = ScoringRules.compute_penalties(scan)

        repo_score = RepoScore(
            repo_name=repo.name,
            repo_full_name=repo.full_name,
            breakdown=breakdown,
            penalties=penalties,
            confidence=self._compute_confidence(scan),
        )
        repo_score.recompute_global_score()
        repo_score.explanations = ScoreExplainabilityBuilder.build(repo, scan, repo_score)

        return repo_score

    @staticmethod
    def _compute_confidence(scan: RepoScanResult) -> float:
        """
        Confidence reflects how much reliable evidence we collected.
        It is not model uncertainty; it is audit completeness.
        """
        score = 0.20

        if scan.local_path:
            score += 0.15

        if scan.structure.layout_type:
            score += 0.10

        if scan.documentation.has_readme or scan.documentation.readme_path:
            score += 0.15

        if scan.testing.has_tests:
            score += 0.10

        if scan.ci.has_github_actions:
            score += 0.10

        if scan.cleanliness.has_gitignore:
            score += 0.05

        scanner_count = len(scan.scanner_summaries)
        if scanner_count >= 5:
            score += 0.15
        elif scanner_count >= 3:
            score += 0.10

        if len(scan.evidence) >= 10:
            score += 0.10
        elif len(scan.evidence) >= 5:
            score += 0.05

        return max(0.0, min(1.0, round(score, 2)))