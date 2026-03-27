from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


class PolicyValidationError(ValueError):
    """
    Raised when a scoring policy is missing required fields
    or contains invalid values.
    """


def _require_non_negative(value: float, field_name: str) -> float:
    if value < 0:
        raise PolicyValidationError(f"'{field_name}' must be >= 0, got {value}.")
    return value


def _require_positive(value: float, field_name: str) -> float:
    if value <= 0:
        raise PolicyValidationError(f"'{field_name}' must be > 0, got {value}.")
    return value


def _require_probability(value: float, field_name: str) -> float:
    if not 0 <= value <= 1:
        raise PolicyValidationError(f"'{field_name}' must be between 0 and 1, got {value}.")
    return value


@dataclass(frozen=True, slots=True)
class ScoringWeights:
    architecture: float
    documentation: float
    testing: float
    technical_depth: float
    portfolio_relevance: float
    maintainability: float

    def __post_init__(self) -> None:
        _require_non_negative(self.architecture, "weights.architecture")
        _require_non_negative(self.documentation, "weights.documentation")
        _require_non_negative(self.testing, "weights.testing")
        _require_non_negative(self.technical_depth, "weights.technical_depth")
        _require_non_negative(self.portfolio_relevance, "weights.portfolio_relevance")
        _require_non_negative(self.maintainability, "weights.maintainability")

        total = self.total
        if abs(total - 100.0) > 1e-9:
            raise PolicyValidationError(
                f"Scoring weights must sum to 100.0, got {total:.4f}."
            )

    @property
    def total(self) -> float:
        return (
            self.architecture
            + self.documentation
            + self.testing
            + self.technical_depth
            + self.portfolio_relevance
            + self.maintainability
        )


@dataclass(frozen=True, slots=True)
class LayoutBonusPolicy:
    well_structured: float
    structured: float
    partially_structured: float

    def __post_init__(self) -> None:
        _require_probability(self.well_structured, "structure_signals.layout_bonus.well_structured")
        _require_probability(self.structured, "structure_signals.layout_bonus.structured")
        _require_probability(
            self.partially_structured,
            "structure_signals.layout_bonus.partially_structured",
        )


@dataclass(frozen=True, slots=True)
class RootFileCountPolicy:
    small_max: int
    small_bonus: float
    crowded_min: int
    crowded_penalty: float

    def __post_init__(self) -> None:
        if self.small_max < 0:
            raise PolicyValidationError(
                f"'structure_signals.root_file_count.small_max' must be >= 0, got {self.small_max}."
            )
        _require_probability(self.small_bonus, "structure_signals.root_file_count.small_bonus")
        if self.crowded_min < 0:
            raise PolicyValidationError(
                f"'structure_signals.root_file_count.crowded_min' must be >= 0, got {self.crowded_min}."
            )
        _require_probability(
            self.crowded_penalty, "structure_signals.root_file_count.crowded_penalty"
        )
        if self.crowded_min <= self.small_max:
            raise PolicyValidationError(
                "structure_signals.root_file_count.crowded_min must be > small_max."
            )


@dataclass(frozen=True, slots=True)
class StructureSignals:
    base_score: float
    src_directory: float
    app_directory: float
    tests_directory: float
    docs_directory: float
    scripts_directory: float
    data_directory: float
    layout_bonus: LayoutBonusPolicy
    root_file_count: RootFileCountPolicy

    def __post_init__(self) -> None:
        _require_probability(self.base_score, "structure_signals.base_score")
        _require_probability(self.src_directory, "structure_signals.src_directory")
        _require_probability(self.app_directory, "structure_signals.app_directory")
        _require_probability(self.tests_directory, "structure_signals.tests_directory")
        _require_probability(self.docs_directory, "structure_signals.docs_directory")
        _require_probability(self.scripts_directory, "structure_signals.scripts_directory")
        _require_probability(self.data_directory, "structure_signals.data_directory")


@dataclass(frozen=True, slots=True)
class WordCountSignalPolicy:
    excellent_threshold: int
    excellent_bonus: float
    strong_threshold: int
    strong_bonus: float
    adequate_threshold: int
    adequate_bonus: float
    minimal_threshold: int
    minimal_bonus: float

    def __post_init__(self) -> None:
        thresholds = [
            self.excellent_threshold,
            self.strong_threshold,
            self.adequate_threshold,
            self.minimal_threshold,
        ]
        if any(value < 0 for value in thresholds):
            raise PolicyValidationError(
                "documentation_signals.readme_word_count thresholds must all be >= 0."
            )
        if not (
            self.excellent_threshold
            >= self.strong_threshold
            >= self.adequate_threshold
            >= self.minimal_threshold
        ):
            raise PolicyValidationError(
                "documentation_signals.readme_word_count thresholds must be descending."
            )

        _require_probability(
            self.excellent_bonus, "documentation_signals.readme_word_count.excellent_bonus"
        )
        _require_probability(
            self.strong_bonus, "documentation_signals.readme_word_count.strong_bonus"
        )
        _require_probability(
            self.adequate_bonus, "documentation_signals.readme_word_count.adequate_bonus"
        )
        _require_probability(
            self.minimal_bonus, "documentation_signals.readme_word_count.minimal_bonus"
        )


@dataclass(frozen=True, slots=True)
class DocumentationSignals:
    readme_presence: float
    readme_word_count: WordCountSignalPolicy
    installation_section: float
    usage_section: float
    architecture_section: float
    results_section: float
    roadmap_section: float
    license_file: float
    env_example: float
    screenshots_or_assets: float

    def __post_init__(self) -> None:
        _require_probability(self.readme_presence, "documentation_signals.readme_presence")
        _require_probability(
            self.installation_section, "documentation_signals.installation_section"
        )
        _require_probability(self.usage_section, "documentation_signals.usage_section")
        _require_probability(
            self.architecture_section, "documentation_signals.architecture_section"
        )
        _require_probability(self.results_section, "documentation_signals.results_section")
        _require_probability(self.roadmap_section, "documentation_signals.roadmap_section")
        _require_probability(self.license_file, "documentation_signals.license_file")
        _require_probability(self.env_example, "documentation_signals.env_example")
        _require_probability(
            self.screenshots_or_assets, "documentation_signals.screenshots_or_assets"
        )


@dataclass(frozen=True, slots=True)
class TestFileCountSignalPolicy:
    excellent_threshold: int
    excellent_bonus: float
    strong_threshold: int
    strong_bonus: float
    adequate_threshold: int
    adequate_bonus: float
    minimal_threshold: int
    minimal_bonus: float
    fallback_bonus: float

    def __post_init__(self) -> None:
        thresholds = [
            self.excellent_threshold,
            self.strong_threshold,
            self.adequate_threshold,
            self.minimal_threshold,
        ]
        if any(value < 0 for value in thresholds):
            raise PolicyValidationError(
                "testing_signals.test_file_count thresholds must all be >= 0."
            )
        if not (
            self.excellent_threshold
            >= self.strong_threshold
            >= self.adequate_threshold
            >= self.minimal_threshold
        ):
            raise PolicyValidationError(
                "testing_signals.test_file_count thresholds must be descending."
            )

        _require_probability(self.excellent_bonus, "testing_signals.test_file_count.excellent_bonus")
        _require_probability(self.strong_bonus, "testing_signals.test_file_count.strong_bonus")
        _require_probability(self.adequate_bonus, "testing_signals.test_file_count.adequate_bonus")
        _require_probability(self.minimal_bonus, "testing_signals.test_file_count.minimal_bonus")
        _require_probability(self.fallback_bonus, "testing_signals.test_file_count.fallback_bonus")


@dataclass(frozen=True, slots=True)
class TestingSignals:
    base_score: float
    test_file_count: TestFileCountSignalPolicy
    framework_detected_bonus: float
    coverage_config_bonus: float
    ci_test_workflow_bonus: float

    def __post_init__(self) -> None:
        _require_probability(self.base_score, "testing_signals.base_score")
        _require_probability(
            self.framework_detected_bonus, "testing_signals.framework_detected_bonus"
        )
        _require_probability(
            self.coverage_config_bonus, "testing_signals.coverage_config_bonus"
        )
        _require_probability(
            self.ci_test_workflow_bonus, "testing_signals.ci_test_workflow_bonus"
        )


@dataclass(frozen=True, slots=True)
class IssueBonusPolicy:
    max_issue_count: int
    bonus: float

    def __post_init__(self) -> None:
        if self.max_issue_count < 0:
            raise PolicyValidationError(
                "technical_depth_signals issue thresholds must be >= 0."
            )
        _require_probability(self.bonus, "technical_depth_signals issue bonus")


@dataclass(frozen=True, slots=True)
class TechnicalDepthSignals:
    base_score: float
    src_or_app_bonus: float
    tests_bonus: float
    docs_bonus: float
    ci_bonus: float
    low_issue_bonus: IssueBonusPolicy
    medium_issue_bonus: IssueBonusPolicy
    technical_keyword_description_bonus: float
    technical_keyword_topics_bonus: float
    primary_language_bonus: float
    architecture_doc_bonus: float
    recognized_languages: tuple[str, ...]
    technical_keywords: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_probability(self.base_score, "technical_depth_signals.base_score")
        _require_probability(self.src_or_app_bonus, "technical_depth_signals.src_or_app_bonus")
        _require_probability(self.tests_bonus, "technical_depth_signals.tests_bonus")
        _require_probability(self.docs_bonus, "technical_depth_signals.docs_bonus")
        _require_probability(self.ci_bonus, "technical_depth_signals.ci_bonus")
        _require_probability(
            self.technical_keyword_description_bonus,
            "technical_depth_signals.technical_keyword_description_bonus",
        )
        _require_probability(
            self.technical_keyword_topics_bonus,
            "technical_depth_signals.technical_keyword_topics_bonus",
        )
        _require_probability(
            self.primary_language_bonus, "technical_depth_signals.primary_language_bonus"
        )
        _require_probability(
            self.architecture_doc_bonus, "technical_depth_signals.architecture_doc_bonus"
        )

        if not self.recognized_languages:
            raise PolicyValidationError(
                "technical_depth_signals.recognized_languages must not be empty."
            )
        if not self.technical_keywords:
            raise PolicyValidationError(
                "technical_depth_signals.technical_keywords must not be empty."
            )


@dataclass(frozen=True, slots=True)
class PortfolioRelevanceSignals:
    base_score: float
    description_bonus: float
    readme_bonus: float
    usage_bonus: float
    results_bonus: float
    screenshots_bonus: float
    homepage_bonus: float
    pages_bonus: float
    topic_bonus_per_topic: float
    topic_bonus_cap: float
    stars_bonus: float
    forks_bonus: float
    tests_bonus: float
    ci_bonus: float

    def __post_init__(self) -> None:
        _require_probability(self.base_score, "portfolio_relevance_signals.base_score")
        _require_probability(
            self.description_bonus, "portfolio_relevance_signals.description_bonus"
        )
        _require_probability(self.readme_bonus, "portfolio_relevance_signals.readme_bonus")
        _require_probability(self.usage_bonus, "portfolio_relevance_signals.usage_bonus")
        _require_probability(self.results_bonus, "portfolio_relevance_signals.results_bonus")
        _require_probability(
            self.screenshots_bonus, "portfolio_relevance_signals.screenshots_bonus"
        )
        _require_probability(self.homepage_bonus, "portfolio_relevance_signals.homepage_bonus")
        _require_probability(self.pages_bonus, "portfolio_relevance_signals.pages_bonus")
        _require_probability(
            self.topic_bonus_per_topic, "portfolio_relevance_signals.topic_bonus_per_topic"
        )
        _require_probability(
            self.topic_bonus_cap, "portfolio_relevance_signals.topic_bonus_cap"
        )
        _require_probability(self.stars_bonus, "portfolio_relevance_signals.stars_bonus")
        _require_probability(self.forks_bonus, "portfolio_relevance_signals.forks_bonus")
        _require_probability(self.tests_bonus, "portfolio_relevance_signals.tests_bonus")
        _require_probability(self.ci_bonus, "portfolio_relevance_signals.ci_bonus")


@dataclass(frozen=True, slots=True)
class MaintainabilitySignals:
    gitignore_present_score: float
    gitignore_missing_score: float
    no_virtualenv_bonus: float
    no_pycache_bonus: float
    no_pytest_cache_bonus: float
    no_build_artifacts_bonus: float
    no_egg_info_bonus: float
    no_oversized_files_bonus: float
    no_suspicious_generated_files_bonus: float

    def __post_init__(self) -> None:
        _require_probability(
            self.gitignore_present_score, "maintainability_signals.gitignore_present_score"
        )
        _require_probability(
            self.gitignore_missing_score, "maintainability_signals.gitignore_missing_score"
        )
        _require_probability(
            self.no_virtualenv_bonus, "maintainability_signals.no_virtualenv_bonus"
        )
        _require_probability(self.no_pycache_bonus, "maintainability_signals.no_pycache_bonus")
        _require_probability(
            self.no_pytest_cache_bonus, "maintainability_signals.no_pytest_cache_bonus"
        )
        _require_probability(
            self.no_build_artifacts_bonus,
            "maintainability_signals.no_build_artifacts_bonus",
        )
        _require_probability(
            self.no_egg_info_bonus, "maintainability_signals.no_egg_info_bonus"
        )
        _require_probability(
            self.no_oversized_files_bonus,
            "maintainability_signals.no_oversized_files_bonus",
        )
        _require_probability(
            self.no_suspicious_generated_files_bonus,
            "maintainability_signals.no_suspicious_generated_files_bonus",
        )


@dataclass(frozen=True, slots=True)
class DynamicOversizedFilesPenaltyPolicy:
    base_points: float
    per_file_points: float
    max_points: float

    def __post_init__(self) -> None:
        _require_non_negative(self.base_points, "dynamic_penalties.oversized_files.base_points")
        _require_non_negative(
            self.per_file_points, "dynamic_penalties.oversized_files.per_file_points"
        )
        _require_non_negative(self.max_points, "dynamic_penalties.oversized_files.max_points")
        if self.max_points < self.base_points:
            raise PolicyValidationError(
                "dynamic_penalties.oversized_files.max_points must be >= base_points."
            )


@dataclass(frozen=True, slots=True)
class DynamicPenaltiesPolicy:
    oversized_files: DynamicOversizedFilesPenaltyPolicy


@dataclass(frozen=True, slots=True)
class ReviewThresholds:
    feature_now_min_score: float
    improve_then_feature_min_score: float
    archive_or_hide_below: float

    def __post_init__(self) -> None:
        _require_non_negative(
            self.feature_now_min_score, "review_thresholds.feature_now_min_score"
        )
        _require_non_negative(
            self.improve_then_feature_min_score,
            "review_thresholds.improve_then_feature_min_score",
        )
        _require_non_negative(
            self.archive_or_hide_below, "review_thresholds.archive_or_hide_below"
        )

        if not (
            self.feature_now_min_score
            >= self.improve_then_feature_min_score
            >= self.archive_or_hide_below
        ):
            raise PolicyValidationError(
                "Review thresholds must satisfy: "
                "feature_now_min_score >= improve_then_feature_min_score >= archive_or_hide_below."
            )


@dataclass(frozen=True, slots=True)
class TieredCountBonusPolicy:
    medium_threshold: int
    medium_bonus: float
    high_threshold: int
    high_bonus: float

    def __post_init__(self) -> None:
        if self.medium_threshold < 0 or self.high_threshold < 0:
            raise PolicyValidationError("Count bonus thresholds must be >= 0.")
        if self.high_threshold < self.medium_threshold:
            raise PolicyValidationError(
                "high_threshold must be >= medium_threshold in tiered count bonus policy."
            )
        _require_probability(self.medium_bonus, "tiered_count_bonus.medium_bonus")
        _require_probability(self.high_bonus, "tiered_count_bonus.high_bonus")
        if self.high_bonus < self.medium_bonus:
            raise PolicyValidationError("high_bonus must be >= medium_bonus.")


@dataclass(frozen=True, slots=True)
class ConfidencePolicy:
    base_score: float
    local_clone_bonus: float
    layout_detected_bonus: float
    readme_bonus: float
    tests_bonus: float
    ci_bonus: float
    gitignore_bonus: float
    scanner_count: TieredCountBonusPolicy
    evidence_count: TieredCountBonusPolicy

    def __post_init__(self) -> None:
        _require_probability(self.base_score, "confidence.base_score")
        _require_probability(self.local_clone_bonus, "confidence.local_clone_bonus")
        _require_probability(self.layout_detected_bonus, "confidence.layout_detected_bonus")
        _require_probability(self.readme_bonus, "confidence.readme_bonus")
        _require_probability(self.tests_bonus, "confidence.tests_bonus")
        _require_probability(self.ci_bonus, "confidence.ci_bonus")
        _require_probability(self.gitignore_bonus, "confidence.gitignore_bonus")


@dataclass(frozen=True, slots=True)
class RankingDecisionBonus:
    feature_now: float
    improve_then_feature: float
    archive_or_hide: float


@dataclass(frozen=True, slots=True)
class RankingPolicy:
    decision_bonus: RankingDecisionBonus
    confidence_weight: float
    blocker_penalty_weight: float
    redundancy_penalty_weight: float

    def __post_init__(self) -> None:
        _require_non_negative(self.confidence_weight, "ranking.confidence_weight")
        _require_non_negative(
            self.blocker_penalty_weight, "ranking.blocker_penalty_weight"
        )
        _require_non_negative(
            self.redundancy_penalty_weight, "ranking.redundancy_penalty_weight"
        )


@dataclass(frozen=True, slots=True)
class RedundancyPolicy:
    strong_overlap_penalty: float
    medium_overlap_penalty: float
    same_category_feature_limit: int

    def __post_init__(self) -> None:
        _require_non_negative(
            self.strong_overlap_penalty, "redundancy.strong_overlap_penalty"
        )
        _require_non_negative(
            self.medium_overlap_penalty, "redundancy.medium_overlap_penalty"
        )
        if self.strong_overlap_penalty < self.medium_overlap_penalty:
            raise PolicyValidationError(
                "redundancy.strong_overlap_penalty must be >= medium_overlap_penalty."
            )
        if self.same_category_feature_limit <= 0:
            raise PolicyValidationError(
                "redundancy.same_category_feature_limit must be > 0."
            )


@dataclass(frozen=True, slots=True)
class SelectionPolicy:
    max_featured_repositories: int

    def __post_init__(self) -> None:
        if self.max_featured_repositories <= 0:
            raise PolicyValidationError(
                "selection.max_featured_repositories must be > 0."
            )


@dataclass(frozen=True, slots=True)
class ScoringPolicy:
    version: str
    weights: ScoringWeights
    structure_signals: StructureSignals
    documentation_signals: DocumentationSignals
    testing_signals: TestingSignals
    technical_depth_signals: TechnicalDepthSignals
    portfolio_relevance_signals: PortfolioRelevanceSignals
    maintainability_signals: MaintainabilitySignals
    penalties: Mapping[str, float]
    dynamic_penalties: DynamicPenaltiesPolicy
    review_thresholds: ReviewThresholds
    confidence: ConfidencePolicy
    ranking: RankingPolicy
    redundancy: RedundancyPolicy
    selection: SelectionPolicy

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise PolicyValidationError("Policy version must be a non-empty string.")

        if not self.penalties:
            raise PolicyValidationError("Policy penalties mapping must not be empty.")

        for penalty_name, penalty_value in self.penalties.items():
            if not penalty_name.strip():
                raise PolicyValidationError("Penalty names must be non-empty strings.")
            _require_non_negative(float(penalty_value), f"penalties.{penalty_name}")

    def penalty_value(self, penalty_name: str, default: float | None = None) -> float:
        if penalty_name in self.penalties:
            return float(self.penalties[penalty_name])
        if default is not None:
            return default
        raise KeyError(f"Penalty '{penalty_name}' is not defined in policy '{self.version}'.")