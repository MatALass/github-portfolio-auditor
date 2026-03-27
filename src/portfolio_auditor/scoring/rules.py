from __future__ import annotations

from dataclasses import dataclass

from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_scan import RepoScanResult
from portfolio_auditor.models.repo_score import PenaltyItem
from portfolio_auditor.scoring.policy_models import ScoringPolicy


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

    Each component returns a ratio in [0, 1], later multiplied by the
    category weight defined in the scoring policy.
    """

    @staticmethod
    def compute_components(
        repo: RepoMetadata,
        scan: RepoScanResult,
        policy: ScoringPolicy,
    ) -> RawScoreComponents:
        return RawScoreComponents(
            architecture_structure_ratio=ScoringRules.compute_architecture_structure_ratio(
                scan, policy
            ),
            documentation_delivery_ratio=ScoringRules.compute_documentation_delivery_ratio(
                scan, policy
            ),
            testing_reliability_ratio=ScoringRules.compute_testing_reliability_ratio(
                scan, policy
            ),
            technical_depth_ratio=ScoringRules.compute_technical_depth_ratio(repo, scan, policy),
            portfolio_relevance_ratio=ScoringRules.compute_portfolio_relevance_ratio(
                repo, scan, policy
            ),
            maintainability_cleanliness_ratio=ScoringRules.compute_cleanliness_ratio(
                scan, policy
            ),
        )

    @staticmethod
    def compute_architecture_structure_ratio(
        scan: RepoScanResult,
        policy: ScoringPolicy,
    ) -> float:
        signals = policy.structure_signals
        score = signals.base_score

        if scan.structure.has_src_dir:
            score += signals.src_directory
        elif scan.structure.has_app_dir:
            score += signals.app_directory

        if scan.structure.has_tests_dir:
            score += signals.tests_directory
        if scan.structure.has_docs_dir:
            score += signals.docs_directory
        if scan.structure.has_scripts_dir:
            score += signals.scripts_directory
        if scan.structure.has_data_dir:
            score += signals.data_directory

        if scan.structure.layout_type == "well_structured":
            score += signals.layout_bonus.well_structured
        elif scan.structure.layout_type == "structured":
            score += signals.layout_bonus.structured
        elif scan.structure.layout_type == "partially_structured":
            score += signals.layout_bonus.partially_structured

        if scan.structure.root_file_count <= signals.root_file_count.small_max:
            score += signals.root_file_count.small_bonus
        elif scan.structure.root_file_count >= signals.root_file_count.crowded_min:
            score -= signals.root_file_count.crowded_penalty

        return ScoringRules._clamp(score)

    @staticmethod
    def compute_documentation_delivery_ratio(
        scan: RepoScanResult,
        policy: ScoringPolicy,
    ) -> float:
        signals = policy.documentation_signals
        score = 0.0

        if scan.documentation.has_readme:
            score += signals.readme_presence

        word_count = scan.documentation.readme_word_count
        score += ScoringRules._word_count_bonus(
            word_count=word_count,
            excellent_threshold=signals.readme_word_count.excellent_threshold,
            excellent_bonus=signals.readme_word_count.excellent_bonus,
            strong_threshold=signals.readme_word_count.strong_threshold,
            strong_bonus=signals.readme_word_count.strong_bonus,
            adequate_threshold=signals.readme_word_count.adequate_threshold,
            adequate_bonus=signals.readme_word_count.adequate_bonus,
            minimal_threshold=signals.readme_word_count.minimal_threshold,
            minimal_bonus=signals.readme_word_count.minimal_bonus,
        )

        if scan.documentation.has_installation_section:
            score += signals.installation_section
        if scan.documentation.has_usage_section:
            score += signals.usage_section
        if scan.documentation.has_architecture_section:
            score += signals.architecture_section
        if scan.documentation.has_results_section:
            score += signals.results_section
        if scan.documentation.has_roadmap_section:
            score += signals.roadmap_section
        if scan.documentation.has_license_file:
            score += signals.license_file
        if scan.documentation.has_env_example:
            score += signals.env_example
        if scan.documentation.has_screenshots_or_assets:
            score += signals.screenshots_or_assets

        return ScoringRules._clamp(score)

    @staticmethod
    def compute_testing_reliability_ratio(
        scan: RepoScanResult,
        policy: ScoringPolicy,
    ) -> float:
        if not scan.testing.has_tests:
            return 0.0

        signals = policy.testing_signals
        score = signals.base_score

        count = scan.testing.test_file_count
        score += ScoringRules._test_file_count_bonus(count, policy)

        if scan.testing.detected_frameworks:
            score += signals.framework_detected_bonus

        if scan.testing.has_coverage_config:
            score += signals.coverage_config_bonus

        if scan.ci.has_test_workflow:
            score += signals.ci_test_workflow_bonus

        return ScoringRules._clamp(score)

    @staticmethod
    def compute_technical_depth_ratio(
        repo: RepoMetadata,
        scan: RepoScanResult,
        policy: ScoringPolicy,
    ) -> float:
        signals = policy.technical_depth_signals
        score = signals.base_score

        if scan.structure.has_src_dir or scan.structure.has_app_dir:
            score += signals.src_or_app_bonus
        if scan.structure.has_tests_dir:
            score += signals.tests_bonus
        if scan.structure.has_docs_dir:
            score += signals.docs_bonus
        if scan.ci.has_github_actions:
            score += signals.ci_bonus

        issue_count = scan.issue_count
        if issue_count <= signals.low_issue_bonus.max_issue_count:
            score += signals.low_issue_bonus.bonus
        elif issue_count <= signals.medium_issue_bonus.max_issue_count:
            score += signals.medium_issue_bonus.bonus

        description = (repo.description or "").lower()
        topics = {topic.lower() for topic in repo.topics.items}
        language = (repo.language or repo.language_stats.primary_language or "").lower()

        technical_keywords = {keyword.lower() for keyword in signals.technical_keywords}
        recognized_languages = {lang.lower() for lang in signals.recognized_languages}

        if any(keyword in description for keyword in technical_keywords):
            score += signals.technical_keyword_description_bonus

        if topics.intersection(technical_keywords):
            score += signals.technical_keyword_topics_bonus

        if language in recognized_languages:
            score += signals.primary_language_bonus

        if scan.documentation.has_architecture_section:
            score += signals.architecture_doc_bonus

        return ScoringRules._clamp(score)

    @staticmethod
    def compute_portfolio_relevance_ratio(
        repo: RepoMetadata,
        scan: RepoScanResult,
        policy: ScoringPolicy,
    ) -> float:
        signals = policy.portfolio_relevance_signals
        score = signals.base_score

        if repo.description:
            score += signals.description_bonus

        if scan.documentation.has_readme:
            score += signals.readme_bonus
        if scan.documentation.has_usage_section:
            score += signals.usage_bonus
        if scan.documentation.has_results_section:
            score += signals.results_bonus
        if scan.documentation.has_screenshots_or_assets:
            score += signals.screenshots_bonus

        if repo.links.homepage:
            score += signals.homepage_bonus
        if repo.flags.has_pages:
            score += signals.pages_bonus

        if repo.topics.items:
            score += min(signals.topic_bonus_cap, len(repo.topics.items) * signals.topic_bonus_per_topic)

        if repo.engagement.stargazers_count > 0:
            score += signals.stars_bonus
        if repo.engagement.forks_count > 0:
            score += signals.forks_bonus

        if scan.testing.has_tests:
            score += signals.tests_bonus
        if scan.ci.has_test_workflow:
            score += signals.ci_bonus

        return ScoringRules._clamp(score)

    @staticmethod
    def compute_cleanliness_ratio(
        scan: RepoScanResult,
        policy: ScoringPolicy,
    ) -> float:
        signals = policy.maintainability_signals

        score = (
            signals.gitignore_present_score
            if scan.cleanliness.has_gitignore
            else signals.gitignore_missing_score
        )

        if not scan.cleanliness.committed_virtualenv:
            score += signals.no_virtualenv_bonus
        if not scan.cleanliness.committed_pycache:
            score += signals.no_pycache_bonus
        if not scan.cleanliness.committed_pytest_cache:
            score += signals.no_pytest_cache_bonus
        if not scan.cleanliness.committed_build_artifacts:
            score += signals.no_build_artifacts_bonus
        if not scan.cleanliness.committed_egg_info:
            score += signals.no_egg_info_bonus
        if not scan.cleanliness.oversized_files:
            score += signals.no_oversized_files_bonus
        if not scan.cleanliness.suspicious_generated_files:
            score += signals.no_suspicious_generated_files_bonus

        return ScoringRules._clamp(score)

    @staticmethod
    def compute_penalties(scan: RepoScanResult, policy: ScoringPolicy) -> list[PenaltyItem]:
        penalties: list[PenaltyItem] = []

        penalties.extend(ScoringRules._penalties_from_cleanliness(scan, policy))
        penalties.extend(ScoringRules._penalties_from_docs(scan, policy))
        penalties.extend(ScoringRules._penalties_from_tests(scan, policy))
        penalties.extend(ScoringRules._penalties_from_structure(scan, policy))

        return penalties

    @staticmethod
    def _penalties_from_cleanliness(
        scan: RepoScanResult,
        policy: ScoringPolicy,
    ) -> list[PenaltyItem]:
        penalties: list[PenaltyItem] = []

        if scan.cleanliness.committed_virtualenv:
            penalties.append(
                PenaltyItem(
                    code="VIRTUALENV_COMMITTED",
                    label="Virtual environment committed",
                    points=policy.penalty_value("VIRTUALENV_COMMITTED"),
                    reason="A committed local virtual environment is a strong negative delivery signal.",
                )
            )

        if scan.cleanliness.committed_pycache:
            penalties.append(
                PenaltyItem(
                    code="PYCACHE_COMMITTED",
                    label="__pycache__ committed",
                    points=policy.penalty_value("PYCACHE_COMMITTED"),
                    reason="Python cache folders should not be versioned.",
                )
            )

        if scan.cleanliness.committed_build_artifacts:
            penalties.append(
                PenaltyItem(
                    code="BUILD_ARTIFACTS_COMMITTED",
                    label="Build artifacts committed",
                    points=policy.penalty_value("BUILD_ARTIFACTS_COMMITTED"),
                    reason="Generated build or cache artifacts reduce repository cleanliness.",
                )
            )

        if scan.cleanliness.committed_egg_info:
            penalties.append(
                PenaltyItem(
                    code="EGG_INFO_COMMITTED",
                    label=".egg-info committed",
                    points=policy.penalty_value("EGG_INFO_COMMITTED"),
                    reason="Packaging metadata should usually be excluded from version control.",
                )
            )

        if scan.cleanliness.oversized_files:
            oversized_policy = policy.dynamic_penalties.oversized_files
            oversized_count = len(scan.cleanliness.oversized_files)
            points = min(
                oversized_policy.max_points,
                oversized_policy.base_points + oversized_count * oversized_policy.per_file_points,
            )
            penalties.append(
                PenaltyItem(
                    code="OVERSIZED_FILES",
                    label="Oversized files detected",
                    points=round(points, 2),
                    reason="Large files can hurt repository clarity and delivery quality.",
                )
            )

        return penalties

    @staticmethod
    def _penalties_from_docs(
        scan: RepoScanResult,
        policy: ScoringPolicy,
    ) -> list[PenaltyItem]:
        penalties: list[PenaltyItem] = []

        if not scan.documentation.has_readme:
            penalties.append(
                PenaltyItem(
                    code="README_MISSING",
                    label="README missing",
                    points=policy.penalty_value("README_MISSING"),
                    reason="A missing README is a major blocker for portfolio and delivery quality.",
                )
            )

        if scan.documentation.has_readme and scan.documentation.readme_word_count < 80:
            penalties.append(
                PenaltyItem(
                    code="README_TOO_SHORT",
                    label="README too short",
                    points=policy.penalty_value("README_TOO_SHORT"),
                    reason="A very short README weakens clarity and recruiter comprehension.",
                )
            )

        if scan.documentation.has_readme and not scan.documentation.has_usage_section:
            penalties.append(
                PenaltyItem(
                    code="USAGE_MISSING",
                    label="Usage instructions missing",
                    points=policy.penalty_value("USAGE_MISSING"),
                    reason="The project is harder to evaluate without clear run instructions.",
                )
            )

        return penalties

    @staticmethod
    def _penalties_from_tests(
        scan: RepoScanResult,
        policy: ScoringPolicy,
    ) -> list[PenaltyItem]:
        penalties: list[PenaltyItem] = []

        if not scan.testing.has_tests:
            penalties.append(
                PenaltyItem(
                    code="NO_TESTS_DETECTED",
                    label="No tests detected",
                    points=policy.penalty_value("NO_TESTS_DETECTED"),
                    reason="The absence of tests weakens reliability and engineering credibility.",
                )
            )
        elif scan.testing.test_file_count < 3:
            penalties.append(
                PenaltyItem(
                    code="WEAK_TEST_BASELINE",
                    label="Weak test baseline",
                    points=policy.penalty_value("WEAK_TEST_BASELINE"),
                    reason="A very small test suite provides limited confidence.",
                )
            )

        if scan.testing.has_tests and not scan.ci.has_test_workflow:
            penalties.append(
                PenaltyItem(
                    code="NO_TEST_CI",
                    label="No CI test workflow",
                    points=policy.penalty_value("NO_TEST_CI"),
                    reason="Tests exist but are not clearly enforced in CI.",
                )
            )

        return penalties

    @staticmethod
    def _penalties_from_structure(
        scan: RepoScanResult,
        policy: ScoringPolicy,
    ) -> list[PenaltyItem]:
        penalties: list[PenaltyItem] = []

        if not scan.structure.has_src_dir and not scan.structure.has_app_dir:
            penalties.append(
                PenaltyItem(
                    code="MAIN_CODE_DIR_MISSING",
                    label="Main code directory missing",
                    points=policy.penalty_value("MAIN_CODE_DIR_MISSING"),
                    reason="A missing dedicated code directory reduces structural clarity.",
                )
            )

        if scan.structure.root_file_count >= policy.structure_signals.root_file_count.crowded_min:
            penalties.append(
                PenaltyItem(
                    code="ROOT_TOO_CROWDED",
                    label="Root overcrowded",
                    points=policy.penalty_value("ROOT_TOO_CROWDED"),
                    reason="A crowded repository root suggests weak organization.",
                )
            )

        return penalties

    @staticmethod
    def _word_count_bonus(
        *,
        word_count: int,
        excellent_threshold: int,
        excellent_bonus: float,
        strong_threshold: int,
        strong_bonus: float,
        adequate_threshold: int,
        adequate_bonus: float,
        minimal_threshold: int,
        minimal_bonus: float,
    ) -> float:
        if word_count >= excellent_threshold:
            return excellent_bonus
        if word_count >= strong_threshold:
            return strong_bonus
        if word_count >= adequate_threshold:
            return adequate_bonus
        if word_count >= minimal_threshold:
            return minimal_bonus
        return 0.0

    @staticmethod
    def _test_file_count_bonus(count: int, policy: ScoringPolicy) -> float:
        signal = policy.testing_signals.test_file_count

        if count >= signal.excellent_threshold:
            return signal.excellent_bonus
        if count >= signal.strong_threshold:
            return signal.strong_bonus
        if count >= signal.adequate_threshold:
            return signal.adequate_bonus
        if count >= signal.minimal_threshold:
            return signal.minimal_bonus
        return signal.fallback_bonus

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, round(value, 4)))