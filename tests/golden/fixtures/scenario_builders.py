from __future__ import annotations

from dataclasses import dataclass

from portfolio_auditor.models.repo_metadata import (
    RepoEngagement,
    RepoFlags,
    RepoLanguageStats,
    RepoLinks,
    RepoMetadata,
    RepoOwner,
    RepoTimestamps,
    RepoTopics,
)
from portfolio_auditor.models.repo_scan import EvidenceItem, RepoScanResult, ScannerSummary


@dataclass(frozen=True, slots=True)
class GoldenPortfolioCase:
    repos: list[RepoMetadata]
    scans: list[RepoScanResult]



def build_golden_portfolio_case() -> GoldenPortfolioCase:
    repos = [
        _build_repo(
            repo_id=1,
            name="portfolio-analytics-platform",
            description="Analytics dashboard and automation pipeline for GitHub portfolio scoring.",
            topics=["analytics", "dashboard", "python", "automation"],
            stars=4,
            forks=1,
            homepage="https://example.com/demo",
        ),
        _build_repo(
            repo_id=2,
            name="portfolio-analytics-dashboard",
            description="Analytics dashboard for GitHub portfolio review with Streamlit and automation.",
            topics=["analytics", "dashboard", "streamlit", "python"],
            stars=1,
            forks=0,
        ),
        _build_repo(
            repo_id=3,
            name="csv-helper-cli",
            description="CLI utility for converting csv exports and small automation tasks.",
            topics=["cli", "automation", "python"],
            stars=0,
            forks=0,
        ),
        _build_repo(
            repo_id=4,
            name="notes-dump",
            description="Random notes and experiments.",
            topics=["notes"],
            stars=0,
            forks=0,
        ),
    ]

    scans = [
        _build_featured_scan(),
        _build_keep_and_improve_scan(),
        _build_merge_or_reposition_scan(),
        _build_make_private_scan(),
    ]

    return GoldenPortfolioCase(repos=repos, scans=scans)



def _build_repo(
    *,
    repo_id: int,
    name: str,
    description: str,
    topics: list[str],
    stars: int,
    forks: int,
    homepage: str | None = None,
) -> RepoMetadata:
    return RepoMetadata(
        id=repo_id,
        name=name,
        full_name=f"user/{name}",
        description=description,
        default_branch="main",
        size_kb=100,
        owner=RepoOwner(login="user", type="User", html_url="https://github.com/user"),
        flags=RepoFlags(),
        engagement=RepoEngagement(stargazers_count=stars, forks_count=forks),
        timestamps=RepoTimestamps(
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-02T00:00:00Z",
            pushed_at="2025-01-03T00:00:00Z",
        ),
        links=RepoLinks(
            html_url=f"https://github.com/user/{name}",
            clone_url=f"https://github.com/user/{name}.git",
            homepage=homepage,
        ),
        language="Python",
        language_stats=RepoLanguageStats(languages={"Python": 1000}),
        topics=RepoTopics(items=topics),
    )



def _build_featured_scan() -> RepoScanResult:
    scan = RepoScanResult(
        repo_name="portfolio-analytics-platform",
        repo_full_name="user/portfolio-analytics-platform",
        local_path=".",
    )
    scan.structure.has_src_dir = True
    scan.structure.has_tests_dir = True
    scan.structure.has_docs_dir = True
    scan.structure.has_scripts_dir = True
    scan.structure.has_data_dir = True
    scan.structure.layout_type = "well_structured"
    scan.structure.root_file_count = 7

    scan.documentation.has_readme = True
    scan.documentation.readme_path = "README.md"
    scan.documentation.readme_word_count = 680
    scan.documentation.has_installation_section = True
    scan.documentation.has_usage_section = True
    scan.documentation.has_architecture_section = True
    scan.documentation.has_results_section = True
    scan.documentation.has_roadmap_section = True
    scan.documentation.has_license_file = True
    scan.documentation.has_env_example = True
    scan.documentation.has_screenshots_or_assets = True

    scan.testing.has_tests = True
    scan.testing.test_file_count = 18
    scan.testing.detected_frameworks = ["pytest"]
    scan.testing.has_coverage_config = True

    scan.ci.has_github_actions = True
    scan.ci.workflow_count = 2
    scan.ci.has_test_workflow = True
    scan.ci.has_lint_workflow = True

    scan.cleanliness.has_gitignore = True

    _add_scanner_summaries(scan, ["structure", "documentation", "testing", "ci", "cleanliness"])
    _add_evidence(scan, 12)
    return scan



def _build_keep_and_improve_scan() -> RepoScanResult:
    scan = RepoScanResult(
        repo_name="portfolio-analytics-dashboard",
        repo_full_name="user/portfolio-analytics-dashboard",
        local_path=".",
    )
    scan.structure.has_app_dir = True
    scan.structure.has_tests_dir = True
    scan.structure.has_docs_dir = True
    scan.structure.layout_type = "structured"
    scan.structure.root_file_count = 11

    scan.documentation.has_readme = True
    scan.documentation.readme_path = "README.md"
    scan.documentation.readme_word_count = 210
    scan.documentation.has_installation_section = True
    scan.documentation.has_usage_section = True
    scan.documentation.has_results_section = True
    scan.documentation.has_license_file = True
    scan.documentation.has_env_example = True

    scan.testing.has_tests = True
    scan.testing.test_file_count = 4
    scan.testing.detected_frameworks = ["pytest"]

    scan.ci.has_github_actions = True
    scan.ci.has_lint_workflow = True

    scan.cleanliness.has_gitignore = True

    _add_scanner_summaries(scan, ["structure", "documentation", "testing", "ci"])
    _add_evidence(scan, 6)
    return scan



def _build_merge_or_reposition_scan() -> RepoScanResult:
    scan = RepoScanResult(
        repo_name="csv-helper-cli",
        repo_full_name="user/csv-helper-cli",
        local_path=".",
    )
    scan.structure.has_src_dir = True
    scan.structure.layout_type = "partially_structured"
    scan.structure.root_file_count = 14

    scan.documentation.has_readme = True
    scan.documentation.readme_path = "README.md"
    scan.documentation.readme_word_count = 95
    scan.documentation.has_usage_section = True

    scan.testing.has_tests = True
    scan.testing.test_file_count = 1
    scan.testing.detected_frameworks = ["pytest"]

    scan.cleanliness.has_gitignore = True
    scan.cleanliness.oversized_files = ["exports/big.csv"]

    _add_scanner_summaries(scan, ["structure", "documentation", "testing"])
    _add_evidence(scan, 4)
    return scan



def _build_make_private_scan() -> RepoScanResult:
    scan = RepoScanResult(
        repo_name="notes-dump",
        repo_full_name="user/notes-dump",
        local_path=".",
    )
    scan.structure.root_file_count = 28

    scan.cleanliness.committed_virtualenv = True
    scan.cleanliness.committed_pycache = True
    scan.cleanliness.has_gitignore = False
    scan.cleanliness.committed_build_artifacts = True
    scan.cleanliness.committed_egg_info = True
    scan.cleanliness.oversized_files = ["dump.bin", "model.pkl"]

    _add_scanner_summaries(scan, ["cleanliness"])
    _add_evidence(scan, 1)
    return scan



def _add_scanner_summaries(scan: RepoScanResult, names: list[str]) -> None:
    for name in names:
        scan.add_scanner_summary(ScannerSummary(scanner_name=name))



def _add_evidence(scan: RepoScanResult, count: int) -> None:
    for index in range(count):
        scan.add_evidence(EvidenceItem(source="golden_test", message=f"evidence-{index}"))
