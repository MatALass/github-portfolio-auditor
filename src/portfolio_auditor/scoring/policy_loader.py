from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from portfolio_auditor.scoring.policy_models import (
    ConfidencePolicy,
    DocumentationSignals,
    DynamicOversizedFilesPenaltyPolicy,
    DynamicPenaltiesPolicy,
    IssueBonusPolicy,
    LayoutBonusPolicy,
    MaintainabilitySignals,
    PolicyValidationError,
    PortfolioRelevanceSignals,
    RankingDecisionBonus,
    RankingPolicy,
    RedundancyPolicy,
    ReviewThresholds,
    RootFileCountPolicy,
    ScoringPolicy,
    ScoringWeights,
    SelectionPolicy,
    StructureSignals,
    TechnicalDepthSignals,
    TestFileCountSignalPolicy,
    TestingSignals,
    TieredCountBonusPolicy,
    WordCountSignalPolicy,
)


class PolicyLoadError(RuntimeError):
    """
    Raised when a scoring policy file cannot be found or parsed.
    """


def load_scoring_policy(version: str = "v1") -> ScoringPolicy:
    """
    Load and validate a scoring policy by version.

    Parameters
    ----------
    version:
        Policy version name without extension, e.g. 'v1'.

    Returns
    -------
    ScoringPolicy
        Fully validated scoring policy.
    """
    path = _resolve_policy_path(version)
    raw_data = _load_yaml(path)
    policy = _build_policy(raw_data)

    if policy.version != version:
        raise PolicyValidationError(
            f"Policy version mismatch: requested '{version}', "
            f"but file declares '{policy.version}'."
        )

    return policy


def _resolve_policy_path(version: str) -> Path:
    if not version.strip():
        raise PolicyLoadError("Policy version must be a non-empty string.")

    base_dir = Path(__file__).resolve().parent / "policies"
    path = base_dir / f"{version}.yaml"

    if not path.exists():
        raise PolicyLoadError(f"Scoring policy file not found: {path}")

    if not path.is_file():
        raise PolicyLoadError(f"Scoring policy path is not a file: {path}")

    return path


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PolicyLoadError(f"Failed to read scoring policy file '{path}': {exc}") from exc

    try:
        loaded = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise PolicyLoadError(f"Failed to parse YAML policy file '{path}': {exc}") from exc

    if loaded is None:
        raise PolicyLoadError(f"Scoring policy file '{path}' is empty.")

    if not isinstance(loaded, dict):
        raise PolicyLoadError(
            f"Scoring policy file '{path}' must contain a top-level mapping."
        )

    return loaded


def _build_policy(data: dict[str, Any]) -> ScoringPolicy:
    version = _require_str(data, "version")

    weights_data = _require_mapping(data, "weights")
    structure_signals_data = _require_mapping(data, "structure_signals")
    documentation_signals_data = _require_mapping(data, "documentation_signals")
    testing_signals_data = _require_mapping(data, "testing_signals")
    technical_depth_data = _require_mapping(data, "technical_depth_signals")
    portfolio_relevance_data = _require_mapping(data, "portfolio_relevance_signals")
    maintainability_data = _require_mapping(data, "maintainability_signals")
    penalties_data = _require_mapping(data, "penalties")
    dynamic_penalties_data = _require_mapping(data, "dynamic_penalties")
    review_thresholds_data = _require_mapping(data, "review_thresholds")
    confidence_data = _require_mapping(data, "confidence")
    ranking_data = _require_mapping(data, "ranking")
    redundancy_data = _require_mapping(data, "redundancy")
    selection_data = _require_mapping(data, "selection")

    layout_bonus_data = _require_mapping(
        structure_signals_data, "layout_bonus", parent="structure_signals"
    )
    root_file_count_data = _require_mapping(
        structure_signals_data, "root_file_count", parent="structure_signals"
    )
    readme_word_count_data = _require_mapping(
        documentation_signals_data, "readme_word_count", parent="documentation_signals"
    )
    test_file_count_data = _require_mapping(
        testing_signals_data, "test_file_count", parent="testing_signals"
    )
    low_issue_bonus_data = _require_mapping(
        technical_depth_data, "low_issue_bonus", parent="technical_depth_signals"
    )
    medium_issue_bonus_data = _require_mapping(
        technical_depth_data, "medium_issue_bonus", parent="technical_depth_signals"
    )
    oversized_files_data = _require_mapping(
        dynamic_penalties_data, "oversized_files", parent="dynamic_penalties"
    )
    scanner_count_data = _require_mapping(
        confidence_data, "scanner_count", parent="confidence"
    )
    evidence_count_data = _require_mapping(
        confidence_data, "evidence_count", parent="confidence"
    )
    decision_bonus_data = _require_mapping(ranking_data, "decision_bonus", parent="ranking")

    penalties: dict[str, float] = {
        str(name): _as_float(value, f"penalties.{name}")
        for name, value in penalties_data.items()
    }

    recognized_languages = _as_str_tuple(
        technical_depth_data.get("recognized_languages"),
        "technical_depth_signals.recognized_languages",
    )
    technical_keywords = _as_str_tuple(
        technical_depth_data.get("technical_keywords"),
        "technical_depth_signals.technical_keywords",
    )

    return ScoringPolicy(
        version=version,
        weights=ScoringWeights(
            architecture=_as_float(weights_data.get("architecture"), "weights.architecture"),
            documentation=_as_float(weights_data.get("documentation"), "weights.documentation"),
            testing=_as_float(weights_data.get("testing"), "weights.testing"),
            technical_depth=_as_float(
                weights_data.get("technical_depth"), "weights.technical_depth"
            ),
            portfolio_relevance=_as_float(
                weights_data.get("portfolio_relevance"), "weights.portfolio_relevance"
            ),
            maintainability=_as_float(
                weights_data.get("maintainability"), "weights.maintainability"
            ),
        ),
        structure_signals=StructureSignals(
            base_score=_as_float(
                structure_signals_data.get("base_score"),
                "structure_signals.base_score",
            ),
            src_directory=_as_float(
                structure_signals_data.get("src_directory"),
                "structure_signals.src_directory",
            ),
            app_directory=_as_float(
                structure_signals_data.get("app_directory"),
                "structure_signals.app_directory",
            ),
            tests_directory=_as_float(
                structure_signals_data.get("tests_directory"),
                "structure_signals.tests_directory",
            ),
            docs_directory=_as_float(
                structure_signals_data.get("docs_directory"),
                "structure_signals.docs_directory",
            ),
            scripts_directory=_as_float(
                structure_signals_data.get("scripts_directory"),
                "structure_signals.scripts_directory",
            ),
            data_directory=_as_float(
                structure_signals_data.get("data_directory"),
                "structure_signals.data_directory",
            ),
            layout_bonus=LayoutBonusPolicy(
                well_structured=_as_float(
                    layout_bonus_data.get("well_structured"),
                    "structure_signals.layout_bonus.well_structured",
                ),
                structured=_as_float(
                    layout_bonus_data.get("structured"),
                    "structure_signals.layout_bonus.structured",
                ),
                partially_structured=_as_float(
                    layout_bonus_data.get("partially_structured"),
                    "structure_signals.layout_bonus.partially_structured",
                ),
            ),
            root_file_count=RootFileCountPolicy(
                small_max=_as_int(
                    root_file_count_data.get("small_max"),
                    "structure_signals.root_file_count.small_max",
                ),
                small_bonus=_as_float(
                    root_file_count_data.get("small_bonus"),
                    "structure_signals.root_file_count.small_bonus",
                ),
                crowded_min=_as_int(
                    root_file_count_data.get("crowded_min"),
                    "structure_signals.root_file_count.crowded_min",
                ),
                crowded_penalty=_as_float(
                    root_file_count_data.get("crowded_penalty"),
                    "structure_signals.root_file_count.crowded_penalty",
                ),
            ),
        ),
        documentation_signals=DocumentationSignals(
            readme_presence=_as_float(
                documentation_signals_data.get("readme_presence"),
                "documentation_signals.readme_presence",
            ),
            readme_word_count=WordCountSignalPolicy(
                excellent_threshold=_as_int(
                    readme_word_count_data.get("excellent_threshold"),
                    "documentation_signals.readme_word_count.excellent_threshold",
                ),
                excellent_bonus=_as_float(
                    readme_word_count_data.get("excellent_bonus"),
                    "documentation_signals.readme_word_count.excellent_bonus",
                ),
                strong_threshold=_as_int(
                    readme_word_count_data.get("strong_threshold"),
                    "documentation_signals.readme_word_count.strong_threshold",
                ),
                strong_bonus=_as_float(
                    readme_word_count_data.get("strong_bonus"),
                    "documentation_signals.readme_word_count.strong_bonus",
                ),
                adequate_threshold=_as_int(
                    readme_word_count_data.get("adequate_threshold"),
                    "documentation_signals.readme_word_count.adequate_threshold",
                ),
                adequate_bonus=_as_float(
                    readme_word_count_data.get("adequate_bonus"),
                    "documentation_signals.readme_word_count.adequate_bonus",
                ),
                minimal_threshold=_as_int(
                    readme_word_count_data.get("minimal_threshold"),
                    "documentation_signals.readme_word_count.minimal_threshold",
                ),
                minimal_bonus=_as_float(
                    readme_word_count_data.get("minimal_bonus"),
                    "documentation_signals.readme_word_count.minimal_bonus",
                ),
            ),
            installation_section=_as_float(
                documentation_signals_data.get("installation_section"),
                "documentation_signals.installation_section",
            ),
            usage_section=_as_float(
                documentation_signals_data.get("usage_section"),
                "documentation_signals.usage_section",
            ),
            architecture_section=_as_float(
                documentation_signals_data.get("architecture_section"),
                "documentation_signals.architecture_section",
            ),
            results_section=_as_float(
                documentation_signals_data.get("results_section"),
                "documentation_signals.results_section",
            ),
            roadmap_section=_as_float(
                documentation_signals_data.get("roadmap_section"),
                "documentation_signals.roadmap_section",
            ),
            license_file=_as_float(
                documentation_signals_data.get("license_file"),
                "documentation_signals.license_file",
            ),
            env_example=_as_float(
                documentation_signals_data.get("env_example"),
                "documentation_signals.env_example",
            ),
            screenshots_or_assets=_as_float(
                documentation_signals_data.get("screenshots_or_assets"),
                "documentation_signals.screenshots_or_assets",
            ),
        ),
        testing_signals=TestingSignals(
            base_score=_as_float(
                testing_signals_data.get("base_score"),
                "testing_signals.base_score",
            ),
            test_file_count=TestFileCountSignalPolicy(
                excellent_threshold=_as_int(
                    test_file_count_data.get("excellent_threshold"),
                    "testing_signals.test_file_count.excellent_threshold",
                ),
                excellent_bonus=_as_float(
                    test_file_count_data.get("excellent_bonus"),
                    "testing_signals.test_file_count.excellent_bonus",
                ),
                strong_threshold=_as_int(
                    test_file_count_data.get("strong_threshold"),
                    "testing_signals.test_file_count.strong_threshold",
                ),
                strong_bonus=_as_float(
                    test_file_count_data.get("strong_bonus"),
                    "testing_signals.test_file_count.strong_bonus",
                ),
                adequate_threshold=_as_int(
                    test_file_count_data.get("adequate_threshold"),
                    "testing_signals.test_file_count.adequate_threshold",
                ),
                adequate_bonus=_as_float(
                    test_file_count_data.get("adequate_bonus"),
                    "testing_signals.test_file_count.adequate_bonus",
                ),
                minimal_threshold=_as_int(
                    test_file_count_data.get("minimal_threshold"),
                    "testing_signals.test_file_count.minimal_threshold",
                ),
                minimal_bonus=_as_float(
                    test_file_count_data.get("minimal_bonus"),
                    "testing_signals.test_file_count.minimal_bonus",
                ),
                fallback_bonus=_as_float(
                    test_file_count_data.get("fallback_bonus"),
                    "testing_signals.test_file_count.fallback_bonus",
                ),
            ),
            framework_detected_bonus=_as_float(
                testing_signals_data.get("framework_detected_bonus"),
                "testing_signals.framework_detected_bonus",
            ),
            coverage_config_bonus=_as_float(
                testing_signals_data.get("coverage_config_bonus"),
                "testing_signals.coverage_config_bonus",
            ),
            ci_test_workflow_bonus=_as_float(
                testing_signals_data.get("ci_test_workflow_bonus"),
                "testing_signals.ci_test_workflow_bonus",
            ),
        ),
        technical_depth_signals=TechnicalDepthSignals(
            base_score=_as_float(
                technical_depth_data.get("base_score"),
                "technical_depth_signals.base_score",
            ),
            src_or_app_bonus=_as_float(
                technical_depth_data.get("src_or_app_bonus"),
                "technical_depth_signals.src_or_app_bonus",
            ),
            tests_bonus=_as_float(
                technical_depth_data.get("tests_bonus"),
                "technical_depth_signals.tests_bonus",
            ),
            docs_bonus=_as_float(
                technical_depth_data.get("docs_bonus"),
                "technical_depth_signals.docs_bonus",
            ),
            ci_bonus=_as_float(
                technical_depth_data.get("ci_bonus"),
                "technical_depth_signals.ci_bonus",
            ),
            low_issue_bonus=IssueBonusPolicy(
                max_issue_count=_as_int(
                    low_issue_bonus_data.get("max_issue_count"),
                    "technical_depth_signals.low_issue_bonus.max_issue_count",
                ),
                bonus=_as_float(
                    low_issue_bonus_data.get("bonus"),
                    "technical_depth_signals.low_issue_bonus.bonus",
                ),
            ),
            medium_issue_bonus=IssueBonusPolicy(
                max_issue_count=_as_int(
                    medium_issue_bonus_data.get("max_issue_count"),
                    "technical_depth_signals.medium_issue_bonus.max_issue_count",
                ),
                bonus=_as_float(
                    medium_issue_bonus_data.get("bonus"),
                    "technical_depth_signals.medium_issue_bonus.bonus",
                ),
            ),
            technical_keyword_description_bonus=_as_float(
                technical_depth_data.get("technical_keyword_description_bonus"),
                "technical_depth_signals.technical_keyword_description_bonus",
            ),
            technical_keyword_topics_bonus=_as_float(
                technical_depth_data.get("technical_keyword_topics_bonus"),
                "technical_depth_signals.technical_keyword_topics_bonus",
            ),
            primary_language_bonus=_as_float(
                technical_depth_data.get("primary_language_bonus"),
                "technical_depth_signals.primary_language_bonus",
            ),
            architecture_doc_bonus=_as_float(
                technical_depth_data.get("architecture_doc_bonus"),
                "technical_depth_signals.architecture_doc_bonus",
            ),
            recognized_languages=recognized_languages,
            technical_keywords=technical_keywords,
        ),
        portfolio_relevance_signals=PortfolioRelevanceSignals(
            base_score=_as_float(
                portfolio_relevance_data.get("base_score"),
                "portfolio_relevance_signals.base_score",
            ),
            description_bonus=_as_float(
                portfolio_relevance_data.get("description_bonus"),
                "portfolio_relevance_signals.description_bonus",
            ),
            readme_bonus=_as_float(
                portfolio_relevance_data.get("readme_bonus"),
                "portfolio_relevance_signals.readme_bonus",
            ),
            usage_bonus=_as_float(
                portfolio_relevance_data.get("usage_bonus"),
                "portfolio_relevance_signals.usage_bonus",
            ),
            results_bonus=_as_float(
                portfolio_relevance_data.get("results_bonus"),
                "portfolio_relevance_signals.results_bonus",
            ),
            screenshots_bonus=_as_float(
                portfolio_relevance_data.get("screenshots_bonus"),
                "portfolio_relevance_signals.screenshots_bonus",
            ),
            homepage_bonus=_as_float(
                portfolio_relevance_data.get("homepage_bonus"),
                "portfolio_relevance_signals.homepage_bonus",
            ),
            pages_bonus=_as_float(
                portfolio_relevance_data.get("pages_bonus"),
                "portfolio_relevance_signals.pages_bonus",
            ),
            topic_bonus_per_topic=_as_float(
                portfolio_relevance_data.get("topic_bonus_per_topic"),
                "portfolio_relevance_signals.topic_bonus_per_topic",
            ),
            topic_bonus_cap=_as_float(
                portfolio_relevance_data.get("topic_bonus_cap"),
                "portfolio_relevance_signals.topic_bonus_cap",
            ),
            stars_bonus=_as_float(
                portfolio_relevance_data.get("stars_bonus"),
                "portfolio_relevance_signals.stars_bonus",
            ),
            forks_bonus=_as_float(
                portfolio_relevance_data.get("forks_bonus"),
                "portfolio_relevance_signals.forks_bonus",
            ),
            tests_bonus=_as_float(
                portfolio_relevance_data.get("tests_bonus"),
                "portfolio_relevance_signals.tests_bonus",
            ),
            ci_bonus=_as_float(
                portfolio_relevance_data.get("ci_bonus"),
                "portfolio_relevance_signals.ci_bonus",
            ),
        ),
        maintainability_signals=MaintainabilitySignals(
            gitignore_present_score=_as_float(
                maintainability_data.get("gitignore_present_score"),
                "maintainability_signals.gitignore_present_score",
            ),
            gitignore_missing_score=_as_float(
                maintainability_data.get("gitignore_missing_score"),
                "maintainability_signals.gitignore_missing_score",
            ),
            no_virtualenv_bonus=_as_float(
                maintainability_data.get("no_virtualenv_bonus"),
                "maintainability_signals.no_virtualenv_bonus",
            ),
            no_pycache_bonus=_as_float(
                maintainability_data.get("no_pycache_bonus"),
                "maintainability_signals.no_pycache_bonus",
            ),
            no_pytest_cache_bonus=_as_float(
                maintainability_data.get("no_pytest_cache_bonus"),
                "maintainability_signals.no_pytest_cache_bonus",
            ),
            no_build_artifacts_bonus=_as_float(
                maintainability_data.get("no_build_artifacts_bonus"),
                "maintainability_signals.no_build_artifacts_bonus",
            ),
            no_egg_info_bonus=_as_float(
                maintainability_data.get("no_egg_info_bonus"),
                "maintainability_signals.no_egg_info_bonus",
            ),
            no_oversized_files_bonus=_as_float(
                maintainability_data.get("no_oversized_files_bonus"),
                "maintainability_signals.no_oversized_files_bonus",
            ),
            no_suspicious_generated_files_bonus=_as_float(
                maintainability_data.get("no_suspicious_generated_files_bonus"),
                "maintainability_signals.no_suspicious_generated_files_bonus",
            ),
        ),
        penalties=penalties,
        dynamic_penalties=DynamicPenaltiesPolicy(
            oversized_files=DynamicOversizedFilesPenaltyPolicy(
                base_points=_as_float(
                    oversized_files_data.get("base_points"),
                    "dynamic_penalties.oversized_files.base_points",
                ),
                per_file_points=_as_float(
                    oversized_files_data.get("per_file_points"),
                    "dynamic_penalties.oversized_files.per_file_points",
                ),
                max_points=_as_float(
                    oversized_files_data.get("max_points"),
                    "dynamic_penalties.oversized_files.max_points",
                ),
            ),
        ),
        review_thresholds=ReviewThresholds(
            feature_now_min_score=_as_float(
                review_thresholds_data.get("feature_now_min_score"),
                "review_thresholds.feature_now_min_score",
            ),
            improve_then_feature_min_score=_as_float(
                review_thresholds_data.get("improve_then_feature_min_score"),
                "review_thresholds.improve_then_feature_min_score",
            ),
            archive_or_hide_below=_as_float(
                review_thresholds_data.get("archive_or_hide_below"),
                "review_thresholds.archive_or_hide_below",
            ),
        ),
        confidence=ConfidencePolicy(
            base_score=_as_float(
                confidence_data.get("base_score"),
                "confidence.base_score",
            ),
            local_clone_bonus=_as_float(
                confidence_data.get("local_clone_bonus"),
                "confidence.local_clone_bonus",
            ),
            layout_detected_bonus=_as_float(
                confidence_data.get("layout_detected_bonus"),
                "confidence.layout_detected_bonus",
            ),
            readme_bonus=_as_float(
                confidence_data.get("readme_bonus"),
                "confidence.readme_bonus",
            ),
            tests_bonus=_as_float(
                confidence_data.get("tests_bonus"),
                "confidence.tests_bonus",
            ),
            ci_bonus=_as_float(
                confidence_data.get("ci_bonus"),
                "confidence.ci_bonus",
            ),
            gitignore_bonus=_as_float(
                confidence_data.get("gitignore_bonus"),
                "confidence.gitignore_bonus",
            ),
            scanner_count=TieredCountBonusPolicy(
                medium_threshold=_as_int(
                    scanner_count_data.get("medium_threshold"),
                    "confidence.scanner_count.medium_threshold",
                ),
                medium_bonus=_as_float(
                    scanner_count_data.get("medium_bonus"),
                    "confidence.scanner_count.medium_bonus",
                ),
                high_threshold=_as_int(
                    scanner_count_data.get("high_threshold"),
                    "confidence.scanner_count.high_threshold",
                ),
                high_bonus=_as_float(
                    scanner_count_data.get("high_bonus"),
                    "confidence.scanner_count.high_bonus",
                ),
            ),
            evidence_count=TieredCountBonusPolicy(
                medium_threshold=_as_int(
                    evidence_count_data.get("medium_threshold"),
                    "confidence.evidence_count.medium_threshold",
                ),
                medium_bonus=_as_float(
                    evidence_count_data.get("medium_bonus"),
                    "confidence.evidence_count.medium_bonus",
                ),
                high_threshold=_as_int(
                    evidence_count_data.get("high_threshold"),
                    "confidence.evidence_count.high_threshold",
                ),
                high_bonus=_as_float(
                    evidence_count_data.get("high_bonus"),
                    "confidence.evidence_count.high_bonus",
                ),
            ),
        ),
        ranking=RankingPolicy(
            decision_bonus=RankingDecisionBonus(
                feature_now=_as_float(
                    decision_bonus_data.get("feature_now"),
                    "ranking.decision_bonus.feature_now",
                ),
                improve_then_feature=_as_float(
                    decision_bonus_data.get("improve_then_feature"),
                    "ranking.decision_bonus.improve_then_feature",
                ),
                archive_or_hide=_as_float(
                    decision_bonus_data.get("archive_or_hide"),
                    "ranking.decision_bonus.archive_or_hide",
                ),
            ),
            confidence_weight=_as_float(
                ranking_data.get("confidence_weight"),
                "ranking.confidence_weight",
            ),
            blocker_penalty_weight=_as_float(
                ranking_data.get("blocker_penalty_weight"),
                "ranking.blocker_penalty_weight",
            ),
            redundancy_penalty_weight=_as_float(
                ranking_data.get("redundancy_penalty_weight"),
                "ranking.redundancy_penalty_weight",
            ),
        ),
        redundancy=RedundancyPolicy(
            strong_overlap_penalty=_as_float(
                redundancy_data.get("strong_overlap_penalty"),
                "redundancy.strong_overlap_penalty",
            ),
            medium_overlap_penalty=_as_float(
                redundancy_data.get("medium_overlap_penalty"),
                "redundancy.medium_overlap_penalty",
            ),
            same_category_feature_limit=_as_int(
                redundancy_data.get("same_category_feature_limit"),
                "redundancy.same_category_feature_limit",
            ),
        ),
        selection=SelectionPolicy(
            max_featured_repositories=_as_int(
                selection_data.get("max_featured_repositories"),
                "selection.max_featured_repositories",
            ),
        ),
    )


def _require_mapping(
    container: dict[str, Any],
    key: str,
    *,
    parent: str | None = None,
) -> dict[str, Any]:
    label = f"{parent}.{key}" if parent else key

    if key not in container:
        raise PolicyValidationError(f"Missing required mapping: '{label}'.")

    value = container[key]
    if not isinstance(value, dict):
        raise PolicyValidationError(f"'{label}' must be a mapping/object.")

    return value


def _require_str(container: dict[str, Any], key: str) -> str:
    if key not in container:
        raise PolicyValidationError(f"Missing required field: '{key}'.")

    value = container[key]
    if not isinstance(value, str):
        raise PolicyValidationError(f"'{key}' must be a string.")

    stripped = value.strip()
    if not stripped:
        raise PolicyValidationError(f"'{key}' must not be empty.")

    return stripped


def _as_float(value: Any, field_name: str) -> float:
    if value is None:
        raise PolicyValidationError(f"Missing required numeric field: '{field_name}'.")

    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise PolicyValidationError(
            f"Field '{field_name}' must be numeric, got {value!r}."
        ) from exc


def _as_int(value: Any, field_name: str) -> int:
    if value is None:
        raise PolicyValidationError(f"Missing required integer field: '{field_name}'.")

    if isinstance(value, bool):
        raise PolicyValidationError(
            f"Field '{field_name}' must be an integer, got boolean {value!r}."
        )

    try:
        int_value = int(value)
    except (TypeError, ValueError) as exc:
        raise PolicyValidationError(
            f"Field '{field_name}' must be an integer, got {value!r}."
        ) from exc

    try:
        float_value = float(value)
    except (TypeError, ValueError) as exc:
        raise PolicyValidationError(
            f"Field '{field_name}' must be numeric/integer-compatible, got {value!r}."
        ) from exc

    if float_value != float(int_value):
        raise PolicyValidationError(
            f"Field '{field_name}' must be an integer value, got {value!r}."
        )

    return int_value


def _as_str_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        raise PolicyValidationError(f"Missing required list field: '{field_name}'.")

    if not isinstance(value, list):
        raise PolicyValidationError(f"Field '{field_name}' must be a list of strings.")

    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise PolicyValidationError(
                f"Field '{field_name}[{index}]' must be a string, got {item!r}."
            )
        stripped = item.strip()
        if not stripped:
            raise PolicyValidationError(
                f"Field '{field_name}[{index}]' must not be empty."
            )
        result.append(stripped)

    if not result:
        raise PolicyValidationError(f"Field '{field_name}' must not be empty.")

    return tuple(result)