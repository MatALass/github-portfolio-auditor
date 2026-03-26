from __future__ import annotations

from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_scan import RepoScanResult
from portfolio_auditor.models.repo_score import RepoScore, ScoreExplanationItem


class ScoreExplainabilityBuilder:
    """
    Build human-readable explanations for score categories.
    """

    @staticmethod
    def build(repo: RepoMetadata, scan: RepoScanResult, score: RepoScore) -> list[ScoreExplanationItem]:
        return [
            ScoreExplainabilityBuilder._architecture_explanation(scan, score),
            ScoreExplainabilityBuilder._documentation_explanation(scan, score),
            ScoreExplainabilityBuilder._testing_explanation(scan, score),
            ScoreExplainabilityBuilder._technical_depth_explanation(repo, scan, score),
            ScoreExplainabilityBuilder._portfolio_explanation(repo, scan, score),
            ScoreExplainabilityBuilder._cleanliness_explanation(scan, score),
        ]

    @staticmethod
    def _architecture_explanation(scan: RepoScanResult, score: RepoScore) -> ScoreExplanationItem:
        points: list[str] = []

        if scan.structure.has_src_dir:
            points.append("Dedicated src/ directory detected.")
        elif scan.structure.has_app_dir:
            points.append("Dedicated app/ directory detected.")
        else:
            points.append("No dedicated main code directory detected.")

        if scan.structure.has_tests_dir:
            points.append("Top-level tests/ directory present.")
        else:
            points.append("Top-level tests/ directory missing.")

        if scan.structure.has_docs_dir:
            points.append("docs/ directory present.")

        points.append(f"Layout type classified as {scan.structure.layout_type or 'unknown'}.")
        points.append(f"Repository root contains {scan.structure.root_file_count} file(s).")

        return ScoreExplanationItem(
            category="architecture_structure",
            summary=(
                f"Architecture & structure scored {score.breakdown.architecture_structure:.2f}/20 "
                "based on layout clarity and folder organization."
            ),
            supporting_points=points,
        )

    @staticmethod
    def _documentation_explanation(scan: RepoScanResult, score: RepoScore) -> ScoreExplanationItem:
        points: list[str] = []

        if scan.documentation.has_readme:
            points.append(f"README detected with about {scan.documentation.readme_word_count} words.")
        else:
            points.append("README missing.")

        if scan.documentation.has_installation_section:
            points.append("Installation/setup guidance detected.")
        else:
            points.append("Installation/setup guidance missing.")

        if scan.documentation.has_usage_section:
            points.append("Usage instructions detected.")
        else:
            points.append("Usage instructions missing.")

        if scan.documentation.has_architecture_section:
            points.append("Architecture/structure section detected.")

        if scan.documentation.has_license_file:
            points.append("License file present.")

        if scan.documentation.has_env_example:
            points.append("Environment example file present.")

        return ScoreExplanationItem(
            category="documentation_delivery",
            summary=(
                f"Documentation & delivery scored {score.breakdown.documentation_delivery:.2f}/20 "
                "based on README completeness and delivery assets."
            ),
            supporting_points=points,
        )

    @staticmethod
    def _testing_explanation(scan: RepoScanResult, score: RepoScore) -> ScoreExplanationItem:
        points: list[str] = []

        if scan.testing.has_tests:
            points.append(f"Detected {scan.testing.test_file_count} test file(s).")
        else:
            points.append("No tests detected.")

        if scan.testing.detected_frameworks:
            points.append(
                f"Detected testing framework(s): {', '.join(scan.testing.detected_frameworks)}."
            )
        else:
            points.append("No explicit testing framework clearly detected.")

        if scan.testing.has_coverage_config:
            points.append("Coverage-related configuration detected.")
        else:
            points.append("Coverage-related configuration not detected.")

        if scan.ci.has_test_workflow:
            points.append("CI appears to run tests.")
        else:
            points.append("CI test workflow not detected.")

        return ScoreExplanationItem(
            category="testing_reliability",
            summary=(
                f"Testing & reliability scored {score.breakdown.testing_reliability:.2f}/15 "
                "based on test presence, size, and CI validation."
            ),
            supporting_points=points,
        )

    @staticmethod
    def _technical_depth_explanation(
        repo: RepoMetadata,
        scan: RepoScanResult,
        score: RepoScore,
    ) -> ScoreExplanationItem:
        points: list[str] = []

        language = repo.language or repo.language_stats.primary_language
        if language:
            points.append(f"Primary language detected: {language}.")
        else:
            points.append("Primary language unclear.")

        if repo.description:
            points.append("Repository description is present.")
        else:
            points.append("Repository description missing.")

        if repo.topics.items:
            points.append(f"Repository exposes {len(repo.topics.items)} topic(s).")

        points.append(f"Total detected issue count: {scan.issue_count}.")

        if scan.documentation.has_architecture_section:
            points.append("Technical structure is partially documented.")
        else:
            points.append("Technical structure is not clearly documented.")

        return ScoreExplanationItem(
            category="technical_depth",
            summary=(
                f"Technical depth scored {score.breakdown.technical_depth:.2f}/15 "
                "using a conservative heuristic based on project signals and structure."
            ),
            supporting_points=points,
        )

    @staticmethod
    def _portfolio_explanation(
        repo: RepoMetadata,
        scan: RepoScanResult,
        score: RepoScore,
    ) -> ScoreExplanationItem:
        points: list[str] = []

        if repo.description:
            points.append("Project has a visible description.")
        else:
            points.append("Project lacks a visible description.")

        if repo.links.homepage:
            points.append("Homepage/demo URL detected.")
        elif repo.flags.has_pages:
            points.append("GitHub Pages appears enabled.")
        else:
            points.append("No homepage/demo URL detected.")

        if scan.documentation.has_results_section:
            points.append("README includes features/results/demo-style content.")
        else:
            points.append("README does not clearly highlight results or demo value.")

        if scan.documentation.has_screenshots_or_assets:
            points.append("Visual/documentation assets detected.")

        if repo.engagement.stargazers_count > 0 or repo.engagement.forks_count > 0:
            points.append(
                f"Engagement signals present (stars={repo.engagement.stargazers_count}, forks={repo.engagement.forks_count})."
            )

        return ScoreExplanationItem(
            category="portfolio_relevance",
            summary=(
                f"Portfolio relevance scored {score.breakdown.portfolio_relevance:.2f}/20 "
                "based on recruiter readability, visibility, and demonstration value."
            ),
            supporting_points=points,
        )

    @staticmethod
    def _cleanliness_explanation(scan: RepoScanResult, score: RepoScore) -> ScoreExplanationItem:
        points: list[str] = []

        if scan.cleanliness.has_gitignore:
            points.append(".gitignore detected.")
        else:
            points.append(".gitignore missing.")

        if scan.cleanliness.committed_virtualenv:
            points.append("Committed virtual environment detected.")
        else:
            points.append("No committed virtual environment detected.")

        if scan.cleanliness.committed_pycache:
            points.append("__pycache__ folders detected.")
        else:
            points.append("No __pycache__ folders detected.")

        if scan.cleanliness.committed_build_artifacts:
            points.append("Build/cache artifacts detected.")
        else:
            points.append("No major build/cache artifacts detected.")

        if scan.cleanliness.oversized_files:
            points.append(f"Oversized files detected: {len(scan.cleanliness.oversized_files)}.")
        else:
            points.append("No oversized files detected.")

        return ScoreExplanationItem(
            category="maintainability_cleanliness",
            summary=(
                f"Maintainability & cleanliness scored {score.breakdown.maintainability_cleanliness:.2f}/10 "
                "based on repository hygiene and committed artifacts."
            ),
            supporting_points=points,
        )