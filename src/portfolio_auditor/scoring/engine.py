from __future__ import annotations

from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_scan import RepoScanResult
from portfolio_auditor.models.repo_score import RepoScore, ScoreBreakdown
from portfolio_auditor.scoring.explainability import ScoreExplainabilityBuilder
from portfolio_auditor.scoring.policy_loader import load_scoring_policy
from portfolio_auditor.scoring.policy_models import ScoringPolicy
from portfolio_auditor.scoring.rules import RawScoreComponents, ScoringRules


class ScoringEngine:
    """
    Deterministic portfolio scoring engine.

    The engine is now policy-driven:
    - scoring weights come from the loaded policy
    - confidence comes from the loaded policy
    - raw component computation is delegated to ScoringRules
    """

    def __init__(self, policy: ScoringPolicy | None = None, policy_version: str = "v1") -> None:
        self.policy = policy or load_scoring_policy(policy_version)

    def score(self, repo: RepoMetadata, scan: RepoScanResult) -> RepoScore:
        components = ScoringRules.compute_components(repo, scan, self.policy)

        breakdown = self._build_breakdown(components)

        penalties = ScoringRules.compute_penalties(scan, self.policy)

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

    def _build_breakdown(self, components: RawScoreComponents) -> ScoreBreakdown:
        weights = self.policy.weights

        return ScoreBreakdown(
            architecture_structure=round(components.architecture_structure_ratio * weights.architecture, 2),
            documentation_delivery=round(components.documentation_delivery_ratio * weights.documentation, 2),
            testing_reliability=round(components.testing_reliability_ratio * weights.testing, 2),
            technical_depth=round(components.technical_depth_ratio * weights.technical_depth, 2),
            portfolio_relevance=round(
                components.portfolio_relevance_ratio * weights.portfolio_relevance, 2
            ),
            maintainability_cleanliness=round(
                components.maintainability_cleanliness_ratio * weights.maintainability,
                2,
            ),
        )

    def _compute_confidence(self, scan: RepoScanResult) -> float:
        """
        Confidence reflects audit completeness / evidence coverage.
        It is policy-driven and remains clamped in [0, 1].
        """
        confidence_policy = self.policy.confidence
        score = confidence_policy.base_score

        if scan.local_path:
            score += confidence_policy.local_clone_bonus

        if scan.structure.layout_type:
            score += confidence_policy.layout_detected_bonus

        if scan.documentation.has_readme or scan.documentation.readme_path:
            score += confidence_policy.readme_bonus

        if scan.testing.has_tests:
            score += confidence_policy.tests_bonus

        if scan.ci.has_github_actions:
            score += confidence_policy.ci_bonus

        if scan.cleanliness.has_gitignore:
            score += confidence_policy.gitignore_bonus

        scanner_count = len(scan.scanner_summaries)
        score += self._tiered_bonus(
            count=scanner_count,
            medium_threshold=confidence_policy.scanner_count.medium_threshold,
            medium_bonus=confidence_policy.scanner_count.medium_bonus,
            high_threshold=confidence_policy.scanner_count.high_threshold,
            high_bonus=confidence_policy.scanner_count.high_bonus,
        )

        evidence_count = len(scan.evidence)
        score += self._tiered_bonus(
            count=evidence_count,
            medium_threshold=confidence_policy.evidence_count.medium_threshold,
            medium_bonus=confidence_policy.evidence_count.medium_bonus,
            high_threshold=confidence_policy.evidence_count.high_threshold,
            high_bonus=confidence_policy.evidence_count.high_bonus,
        )

        return max(0.0, min(1.0, round(score, 2)))

    @staticmethod
    def _tiered_bonus(
        *,
        count: int,
        medium_threshold: int,
        medium_bonus: float,
        high_threshold: int,
        high_bonus: float,
    ) -> float:
        if count >= high_threshold:
            return high_bonus
        if count >= medium_threshold:
            return medium_bonus
        return 0.0