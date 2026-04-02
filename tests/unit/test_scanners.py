from __future__ import annotations

"""
tests/unit/test_scanners.py

Unit tests for DocumentationScanner and TestingScanner.

Each test builds a temporary directory that simulates a repository layout,
then runs the scanner and asserts on the resulting ScannerSummary and
RepoScanResult fields.
"""

import textwrap
from pathlib import Path

import pytest

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
from portfolio_auditor.scanners.documentation_scanner import DocumentationScanner
from portfolio_auditor.scanners.testing_scanner import TestingScanner


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_repo(name: str = "test-repo") -> RepoMetadata:
    """Build a minimal RepoMetadata suitable for scanner tests."""
    return RepoMetadata(
        id=1,
        name=name,
        full_name=f"user/{name}",
        description=None,
        owner=RepoOwner(login="user", type="User"),
        links=RepoLinks(html_url=f"https://github.com/user/{name}"),
        timestamps=RepoTimestamps(),
        engagement=RepoEngagement(),
        flags=RepoFlags(),
        language_stats=RepoLanguageStats(),
        topics=RepoTopics(),
    )


def _make_scan(repo: RepoMetadata, local_path: Path) -> RepoScanResult:
    return RepoScanResult(
        repo_name=repo.name,
        repo_full_name=repo.full_name,
        local_path=str(local_path),
    )


# ---------------------------------------------------------------------------
# DocumentationScanner tests
# ---------------------------------------------------------------------------


class TestDocumentationScanner:
    scanner = DocumentationScanner()

    def test_no_readme_raises_issue(self, tmp_path: Path) -> None:
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        issue_codes = {issue.code for issue in summary.issues}
        assert "README_MISSING" in issue_codes
        assert not scan.documentation.has_readme
        assert summary.passed is False

    def test_readme_detected_and_word_count(self, tmp_path: Path) -> None:
        readme = tmp_path / "README.md"
        readme.write_text("# My project\n\n" + " ".join(["word"] * 200), encoding="utf-8")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        assert scan.documentation.has_readme is True
        assert scan.documentation.readme_word_count >= 200
        issue_codes = {issue.code for issue in summary.issues}
        assert "README_MISSING" not in issue_codes
        assert "README_TOO_SHORT" not in issue_codes

    def test_short_readme_raises_issue(self, tmp_path: Path) -> None:
        readme = tmp_path / "README.md"
        readme.write_text("# Hi\n\nToo short.", encoding="utf-8")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        issue_codes = {issue.code for issue in summary.issues}
        assert "README_TOO_SHORT" in issue_codes

    def test_installation_section_detected(self, tmp_path: Path) -> None:
        readme = tmp_path / "README.md"
        readme.write_text(
            textwrap.dedent("""\
                # My project

                ## Installation

                Run `pip install mypackage`.

                Some more words to pass the minimum word count threshold for the scanner
                so that the README_TOO_SHORT issue is not raised and we only test the
                installation detection logic independently.
            """),
            encoding="utf-8",
        )
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        self.scanner.scan(repo, tmp_path, scan)

        assert scan.documentation.has_installation_section is True

    def test_usage_section_detected(self, tmp_path: Path) -> None:
        readme = tmp_path / "README.md"
        readme.write_text(
            textwrap.dedent("""\
                # My project

                ## Usage

                Run `python main.py` to start the application.  More details below.
                Adding extra words so the README is long enough to avoid the too-short
                issue flagging, which would distract from the usage detection assertion.
            """),
            encoding="utf-8",
        )
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        self.scanner.scan(repo, tmp_path, scan)

        assert scan.documentation.has_usage_section is True

    def test_license_detected(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# project\n\n" + "word " * 150, encoding="utf-8")
        (tmp_path / "LICENSE").write_text("MIT License", encoding="utf-8")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        assert scan.documentation.has_license_file is True
        issue_codes = {issue.code for issue in summary.issues}
        assert "LICENSE_MISSING" not in issue_codes

    def test_env_example_detected(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# project\n\n" + "word " * 150, encoding="utf-8")
        (tmp_path / ".env.example").write_text("API_KEY=your_key", encoding="utf-8")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        self.scanner.scan(repo, tmp_path, scan)

        assert scan.documentation.has_env_example is True

    def test_assets_dir_detected(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# project\n\n" + "word " * 150, encoding="utf-8")
        (tmp_path / "assets").mkdir()
        (tmp_path / "assets" / "screenshot.png").write_bytes(b"fake")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        self.scanner.scan(repo, tmp_path, scan)

        assert scan.documentation.has_screenshots_or_assets is True

    def test_score_hint_increases_with_quality(self, tmp_path: Path) -> None:
        """A well-documented repo should yield a higher score_hint than a minimal one."""
        # Minimal: short README only
        minimal_dir = tmp_path / "minimal"
        minimal_dir.mkdir()
        (minimal_dir / "README.md").write_text("# x\n\nHi.", encoding="utf-8")
        repo = _make_repo("minimal")
        scan_min = _make_scan(repo, minimal_dir)
        summary_min = self.scanner.scan(repo, minimal_dir, scan_min)

        # Full: long README with multiple sections + licence + assets
        full_dir = tmp_path / "full"
        full_dir.mkdir()
        (full_dir / "README.md").write_text(
            textwrap.dedent("""\
                # Full project

                ## Installation
                Run pip install.

                ## Usage
                Run main.py.

                ## Architecture
                Layered design.

                ## Results
                Benchmarks and demos.
            """)
            + "word " * 300,
            encoding="utf-8",
        )
        (full_dir / "LICENSE").write_text("MIT", encoding="utf-8")
        (full_dir / ".env.example").write_text("KEY=value", encoding="utf-8")
        (full_dir / "assets").mkdir()
        (full_dir / "assets" / "img.png").write_bytes(b"x")
        repo_full = _make_repo("full")
        scan_full = _make_scan(repo_full, full_dir)
        summary_full = self.scanner.scan(repo_full, full_dir, scan_full)

        assert summary_full.score_hint > summary_min.score_hint

    def test_nonexistent_repo_raises(self, tmp_path: Path) -> None:
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path / "does_not_exist")

        with pytest.raises((FileNotFoundError, NotADirectoryError)):
            self.scanner.scan(repo, tmp_path / "does_not_exist", scan)


# ---------------------------------------------------------------------------
# TestingScanner tests
# ---------------------------------------------------------------------------


class TestTestingScanner:
    scanner = TestingScanner()

    def test_no_tests_raises_issue(self, tmp_path: Path) -> None:
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        issue_codes = {issue.code for issue in summary.issues}
        assert "NO_TESTS_DETECTED" in issue_codes
        assert not scan.testing.has_tests

    def test_tests_directory_detected(self, tmp_path: Path) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_something.py").write_text("def test_pass(): assert True", encoding="utf-8")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        assert scan.testing.has_tests is True
        assert scan.testing.test_file_count >= 1
        issue_codes = {issue.code for issue in summary.issues}
        assert "NO_TESTS_DETECTED" not in issue_codes

    def test_pytest_framework_detected_via_pyproject(self, tmp_path: Path) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_x.py").write_text("def test_x(): pass", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\ntestpaths = ['tests']\n", encoding="utf-8"
        )
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        self.scanner.scan(repo, tmp_path, scan)

        assert "pytest" in scan.testing.detected_frameworks or scan.testing.has_pytest_config

    def test_multiple_test_files_counted(self, tmp_path: Path) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        for i in range(5):
            (tests_dir / f"test_{i}.py").write_text("def test_pass(): assert True", encoding="utf-8")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        self.scanner.scan(repo, tmp_path, scan)

        assert scan.testing.test_file_count >= 5

    def test_coverage_config_detected(self, tmp_path: Path) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_x.py").write_text("def test_x(): pass", encoding="utf-8")
        (tmp_path / ".coveragerc").write_text("[run]\nbranch = true\n", encoding="utf-8")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        self.scanner.scan(repo, tmp_path, scan)

        assert scan.testing.has_coverage_config is True

    def test_score_hint_increases_with_more_tests(self, tmp_path: Path) -> None:
        # Few tests
        few_dir = tmp_path / "few"
        few_dir.mkdir()
        (few_dir / "tests").mkdir()
        (few_dir / "tests" / "test_a.py").write_text("def test_pass(): assert True", encoding="utf-8")
        repo_few = _make_repo("few")
        scan_few = _make_scan(repo_few, few_dir)
        summary_few = self.scanner.scan(repo_few, few_dir, scan_few)

        # Many tests
        many_dir = tmp_path / "many"
        many_dir.mkdir()
        (many_dir / "tests").mkdir()
        for i in range(15):
            (many_dir / "tests" / f"test_{i}.py").write_text(
                f"def test_{i}(): assert True", encoding="utf-8"
            )
        (many_dir / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\ntestpaths=['tests']\n[tool.coverage.run]\nbranch=true\n",
            encoding="utf-8",
        )
        repo_many = _make_repo("many")
        scan_many = _make_scan(repo_many, many_dir)
        summary_many = self.scanner.scan(repo_many, many_dir, scan_many)

        assert summary_many.score_hint > summary_few.score_hint

    def test_nonexistent_repo_raises(self, tmp_path: Path) -> None:
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path / "ghost")

        with pytest.raises((FileNotFoundError, NotADirectoryError)):
            self.scanner.scan(repo, tmp_path / "ghost", scan)
