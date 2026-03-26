from __future__ import annotations

from dataclasses import dataclass

from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_scan import RepoScanResult
from portfolio_auditor.models.repo_score import PenaltyItem


@dataclass(frozen=True, slots=True)
class RawScoreComponents:
    architecture_structure_ratio: float
    documentation_delivery_ratio: float
    testing_reliability_ratio: float
    technical_depth_ratio: float
    portfolio_relevance_ratio: float
    maintainability_cleanliness_ratio: float


class ScoringRules:
    """
    Deterministic scoring rules.

    Each component returns a ratio in [0, 1], later multiplied by the weight.
    """

    @staticmethod
    def compute_components(repo: RepoMetadata, scan: RepoScanResult) -> RawScoreComponents:
        return RawScoreComponents(
            architecture_structure_ratio=ScoringRules.compute_architecture_structure_ratio(scan),
            documentation_delivery_ratio=ScoringRules.compute_documentation_delivery_ratio(scan),
            testing_reliability_ratio=ScoringRules.compute_testing_reliability_ratio(scan),
            technical_depth_ratio=ScoringRules.compute_technical_depth_ratio(repo, scan),
            portfolio_relevance_ratio=ScoringRules.compute_portfolio_relevance_ratio(repo, scan),
            maintainability_cleanliness_ratio=ScoringRules.compute_cleanliness_ratio(scan),
        )

    @staticmethod
    def compute_architecture_structure_ratio(scan: RepoScanResult) -> float:
        score = 0.1

        if scan.structure.has_src_dir:
            score += 0.35
        elif scan.structure.has_app_dir:
            score += 0.25

        if scan.structure.has_tests_dir:
            score += 0.15
        if scan.structure.has_docs_dir:
            score += 0.10
        if scan.structure.has_scripts_dir:
            score += 0.05
        if scan.structure.has_data_dir:
            score += 0.05

        if scan.structure.layout_type == "well_structured":
            score += 0.15
        elif scan.structure.layout_type == "structured":
            score += 0.10
        elif scan.structure.layout_type == "partially_structured":
            score += 0.05

        if scan.structure.root_file_count <= 10:
            score += 0.05
        elif scan.structure.root_file_count > 20:
            score -= 0.10

        return ScoringRules._clamp(score)

    @staticmethod
    def compute_documentation_delivery_ratio(scan: RepoScanResult) -> float:
        score = 0.0

        if scan.documentation.has_readme:
            score += 0.30

        word_count = scan.documentation.readme_word_count
        if word_count >= 500:
            score += 0.15
        elif word_count >= 250:
            score += 0.12
        elif word_count >= 120:
            score += 0.08
        elif word_count >= 60:
            score += 0.04

        if scan.documentation.has_installation_section:
            score += 0.12
        if scan.documentation.has_usage_section:
            score += 0.12
        if scan.documentation.has_architecture_section:
            score += 0.10
        if scan.documentation.has_results_section:
            score += 0.07
        if scan.documentation.has_roadmap_section:
            score += 0.05
        if scan.documentation.has_license_file:
            score += 0.04
        if scan.documentation.has_env_example:
            score += 0.03
        if scan.documentation.has_screenshots_or_assets:
            score += 0.02

        return ScoringRules._clamp(score)

    @staticmethod
    def compute_testing_reliability_ratio(scan: RepoScanResult) -> float:
        if not scan.testing.has_tests:
            return 0.0

        score = 0.30

        count = scan.testing.test_file_count
        if count >= 20:
            score += 0.30
        elif count >= 10:
            score += 0.25
        elif count >= 5:
            score += 0.20
        elif count >= 3:
            score += 0.10
        else:
            score += 0.05

        if scan.testing.detected_frameworks:
            score += 0.20

        if scan.testing.has_coverage_config:
            score += 0.10

        if scan.ci.has_test_workflow:
            score += 0.10

        return ScoringRules._clamp(score)

    @staticmethod
    def compute_technical_depth_ratio(repo: RepoMetadata, scan: RepoScanResult) -> float:
        """
        V1 heuristic. This is intentionally conservative.
        It estimates technical depth using available metadata + structure signals.
        """

        score = 0.20

        if scan.structure.has_src_dir or scan.structure.has_app_dir:
            score += 0.10
        if scan.structure.has_tests_dir:
            score += 0.05
        if scan.structure.has_docs_dir:
            score += 0.05
        if scan.ci.has_github_actions:
            score += 0.05

        issue_count = scan.issue_count
        if issue_count <= 3:
            score += 0.10
        elif issue_count <= 6:
            score += 0.05

        description = (repo.description or "").lower()
        topics = set(repo.topics.items)
        language = (repo.language or repo.language_stats.primary_language or "").lower()

        technical_keywords = {
            "api",
            "dashboard",
            "analytics",
            "data",
            "pipeline",
            "ml",
            "machine-learning",
            "cli",
            "automation",
            "streamlit",
            "nextjs",
            "typescript",
            "python",
            "sql",
            "bi",
        }

        if any(keyword in description for keyword in technical_keywords):
            score += 0.15

        if topics.intersection(technical_keywords):
            score += 0.15

        if language in {"python", "typescript", "javascript", "sql", "go", "rust"}:
            score += 0.10

        if scan.documentation.has_architecture_section:
            score += 0.05

        return ScoringRules._clamp(score)

    @staticmethod
    def compute_portfolio_relevance_ratio(repo: RepoMetadata, scan: RepoScanResult) -> float:
        """
        V1 heuristic for recruiter/portfolio value.
        """

        score = 0.15

        if repo.description:
            score += 0.10

        if scan.documentation.has_readme:
            score += 0.20
        if scan.documentation.has_usage_section:
            score += 0.10
        if scan.documentation.has_results_section:
            score += 0.08
        if scan.documentation.has_screenshots_or_assets:
            score += 0.07

        if repo.links.homepage:
            score += 0.08
        if repo.flags.has_pages:
            score += 0.05

        if repo.topics.items:
            score += min(0.07, len(repo.topics.items) * 0.01)

        if repo.engagement.stargazers_count > 0:
            score += 0.03
        if repo.engagement.forks_count > 0:
            score += 0.02

        if scan.testing.has_tests:
            score += 0.05
        if scan.ci.has_test_workflow:
            score += 0.05

        return ScoringRules._clamp(score)

    @staticmethod
    def compute_cleanliness_ratio(scan: RepoScanResult) -> float:
        score = 0.60 if scan.cleanliness.has_gitignore else 0.10

        if not scan.cleanliness.committed_virtualenv:
            score += 0.10
        if not scan.cleanliness.committed_pycache:
            score += 0.08
        if not scan.cleanliness.committed_pytest_cache:
            score += 0.04
        if not scan.cleanliness.committed_build_artifacts:
            score += 0.08
        if not scan.cleanliness.committed_egg_info:
            score += 0.03
        if not scan.cleanliness.oversized_files:
            score += 0.04
        if not scan.cleanliness.suspicious_generated_files:
            score += 0.03

        return ScoringRules._clamp(score)

    @staticmethod
    def compute_penalties(scan: RepoScanResult) -> list[PenaltyItem]:
        penalties: list[PenaltyItem] = []

        penalties.extend(ScoringRules._penalties_from_cleanliness(scan))
        penalties.extend(ScoringRules._penalties_from_docs(scan))
        penalties.extend(ScoringRules._penalties_from_tests(scan))
        penalties.extend(ScoringRules._penalties_from_structure(scan))

        return penalties

    @staticmethod
    def _penalties_from_cleanliness(scan: RepoScanResult) -> list[PenaltyItem]:
        penalties: list[PenaltyItem] = []

        if scan.cleanliness.committed_virtualenv:
            penalties.append(
                PenaltyItem(
                    code="VIRTUALENV_COMMITTED",
                    label="Virtual environment committed",
                    points=8.0,
                    reason="A committed local virtual environment is a strong negative delivery signal.",
                )
            )

        if scan.cleanliness.committed_pycache:
            penalties.append(
                PenaltyItem(
                    code="PYCACHE_COMMITTED",
                    label="__pycache__ committed",
                    points=3.0,
                    reason="Python cache folders should not be versioned.",
                )
            )

        if scan.cleanliness.committed_build_artifacts:
            penalties.append(
                PenaltyItem(
                    code="BUILD_ARTIFACTS_COMMITTED",
                    label="Build artifacts committed",
                    points=3.0,
                    reason="Generated build or cache artifacts reduce repository cleanliness.",
                )
            )

        if scan.cleanliness.committed_egg_info:
            penalties.append(
                PenaltyItem(
                    code="EGG_INFO_COMMITTED",
                    label=".egg-info committed",
                    points=1.5,
                    reason="Packaging metadata should usually be excluded from version control.",
                )
            )

        if scan.cleanliness.oversized_files:
            penalties.append(
                PenaltyItem(
                    code="OVERSIZED_FILES",
                    label="Oversized files detected",
                    points=min(4.0, 1.0 + len(scan.cleanliness.oversized_files) * 0.5),
                    reason="Large files can hurt repository clarity and delivery quality.",
                )
            )

        return penalties

    @staticmethod
    def _penalties_from_docs(scan: RepoScanResult) -> list[PenaltyItem]:
        penalties: list[PenaltyItem] = []

        if not scan.documentation.has_readme:
            penalties.append(
                PenaltyItem(
                    code="README_MISSING",
                    label="README missing",
                    points=10.0,
                    reason="A missing README is a major blocker for portfolio and delivery quality.",
                )
            )

        if scan.documentation.has_readme and scan.documentation.readme_word_count < 80:
            penalties.append(
                PenaltyItem(
                    code="README_TOO_SHORT",
                    label="README too short",
                    points=3.0,
                    reason="A very short README weakens clarity and recruiter comprehension.",
                )
            )

        if scan.documentation.has_readme and not scan.documentation.has_usage_section:
            penalties.append(
                PenaltyItem(
                    code="USAGE_MISSING",
                    label="Usage instructions missing",
                    points=2.5,
                    reason="The project is harder to evaluate without clear run instructions.",
                )
            )

        return penalties

    @staticmethod
    def _penalties_from_tests(scan: RepoScanResult) -> list[PenaltyItem]:
        penalties: list[PenaltyItem] = []

        if not scan.testing.has_tests:
            penalties.append(
                PenaltyItem(
                    code="NO_TESTS_DETECTED",
                    label="No tests detected",
                    points=6.0,
                    reason="The absence of tests weakens reliability and engineering credibility.",
                )
            )
        elif scan.testing.test_file_count < 3:
            penalties.append(
                PenaltyItem(
                    code="WEAK_TEST_BASELINE",
                    label="Weak test baseline",
                    points=2.0,
                    reason="A very small test suite provides limited confidence.",
                )
            )

        if scan.testing.has_tests and not scan.ci.has_test_workflow:
            penalties.append(
                PenaltyItem(
                    code="NO_TEST_CI",
                    label="No CI test workflow",
                    points=2.5,
                    reason="Tests exist but are not clearly enforced in CI.",
                )
            )

        return penalties

    @staticmethod
    def _penalties_from_structure(scan: RepoScanResult) -> list[PenaltyItem]:
        penalties: list[PenaltyItem] = []

        if not scan.structure.has_src_dir and not scan.structure.has_app_dir:
            penalties.append(
                PenaltyItem(
                    code="MAIN_CODE_DIR_MISSING",
                    label="Main code directory missing",
                    points=2.5,
                    reason="A missing dedicated code directory reduces structural clarity.",
                )
            )

        if scan.structure.root_file_count > 20:
            penalties.append(
                PenaltyItem(
                    code="ROOT_TOO_CROWDED",
                    label="Root overcrowded",
                    points=2.0,
                    reason="A crowded repository root suggests weak organization.",
                )
            )

        return penalties

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, round(value, 4)))