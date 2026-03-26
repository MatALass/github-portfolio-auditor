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
from portfolio_auditor.models.repo_scan import RepoScanResult
from portfolio_auditor.scoring.engine import ScoringEngine


def build_repo() -> RepoMetadata:
    return RepoMetadata(
        id=1,
        name="example",
        full_name="user/example",
        description="Example repo",
        default_branch="main",
        size_kb=42,
        owner=RepoOwner(login="user", type="User", html_url="https://github.com/user"),
        flags=RepoFlags(),
        engagement=RepoEngagement(),
        timestamps=RepoTimestamps(
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-02T00:00:00Z",
            pushed_at="2025-01-03T00:00:00Z",
        ),
        links=RepoLinks(
            html_url="https://github.com/user/example",
            clone_url="https://github.com/user/example.git",
        ),
        language="Python",
        language_stats=RepoLanguageStats(languages={"Python": 1000}),
        topics=RepoTopics(items=["python", "audit"]),
    )


def test_scoring_engine_penalizes_missing_basics() -> None:
    repo = build_repo()
    scan = RepoScanResult(repo_name="example", repo_full_name="user/example", local_path=".")

    score = ScoringEngine().score(repo, scan)

    assert score.global_score < 60
    assert score.total_penalties > 0
    assert score.score_label in {"weak", "fair", "good"}


def test_scoring_engine_rewards_documented_and_tested_repo() -> None:
    repo = build_repo()
    scan = RepoScanResult(repo_name="example", repo_full_name="user/example", local_path=".")
    scan.structure.has_src_dir = True
    scan.structure.has_tests_dir = True
    scan.structure.layout_type = "src"
    scan.documentation.has_readme = True
    scan.documentation.readme_path = "README.md"
    scan.documentation.readme_word_count = 320
    scan.documentation.has_installation_section = True
    scan.documentation.has_usage_section = True
    scan.documentation.has_architecture_section = True
    scan.testing.has_tests = True
    scan.testing.test_file_count = 6
    scan.testing.detected_frameworks = ["pytest"]
    scan.ci.has_github_actions = True
    scan.ci.has_test_workflow = True
    scan.cleanliness.has_gitignore = True

    score = ScoringEngine().score(repo, scan)

    assert score.global_score >= 70
    assert score.confidence >= 0.75
    assert score.total_penalties == 0