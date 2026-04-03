"""
tests/unit/test_scanners_extended.py

Unit tests for CiScanner, DeliveryCleanlinessScanner, and StructureScanner.

Follows the same conventions as test_scanners.py:
- tmp_path fixture for filesystem isolation
- _make_repo / _make_scan helpers
- FileNotFoundError expected for missing paths
"""

from __future__ import annotations

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
from portfolio_auditor.scanners.ci_scanner import CiScanner
from portfolio_auditor.scanners.delivery_cleanliness_scanner import DeliveryCleanlinessScanner
from portfolio_auditor.scanners.structure_scanner import StructureScanner

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_repo(name: str = "test-repo") -> RepoMetadata:
    return RepoMetadata(
        id=1,
        name=name,
        full_name=f"user/{name}",
        description=None,
        owner=RepoOwner(login="user", type="User"),
        links=RepoLinks(html_url=f"https://github.com/user/{name}"),
        timestamps=RepoTimestamps(
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-02T00:00:00Z",
            pushed_at="2025-01-03T00:00:00Z",
        ),
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
# CiScanner
# ---------------------------------------------------------------------------


class TestCiScanner:
    scanner = CiScanner()

    def test_no_workflows_dir_raises_issue(self, tmp_path: Path) -> None:
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        issue_codes = {i.code for i in summary.issues}
        assert "CI_MISSING" in issue_codes
        assert scan.ci.has_github_actions is False

    def test_workflow_file_detected(self, tmp_path: Path) -> None:
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("name: CI\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pytest\n", encoding="utf-8")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        assert scan.ci.has_github_actions is True
        assert scan.ci.workflow_count == 1
        issue_codes = {i.code for i in summary.issues}
        assert "CI_MISSING" not in issue_codes

    def test_test_workflow_detected(self, tmp_path: Path) -> None:
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "test.yml").write_text("steps:\n  - run: pytest tests/\n", encoding="utf-8")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        self.scanner.scan(repo, tmp_path, scan)

        assert scan.ci.has_test_workflow is True

    def test_lint_workflow_detected(self, tmp_path: Path) -> None:
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "lint.yml").write_text("steps:\n  - run: ruff check .\n", encoding="utf-8")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        self.scanner.scan(repo, tmp_path, scan)

        assert scan.ci.has_lint_workflow is True

    def test_no_test_workflow_raises_issue(self, tmp_path: Path) -> None:
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "deploy.yml").write_text("steps:\n  - run: echo deploy\n", encoding="utf-8")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        assert scan.ci.has_github_actions is True
        assert scan.ci.has_test_workflow is False
        issue_codes = {i.code for i in summary.issues}
        assert "CI_TESTS_NOT_DETECTED" in issue_codes

    def test_score_hint_increases_with_richer_ci(self, tmp_path: Path) -> None:
        # No CI
        bare_dir = tmp_path / "bare"
        bare_dir.mkdir()
        repo_bare = _make_repo("bare")
        scan_bare = _make_scan(repo_bare, bare_dir)
        summary_bare = self.scanner.scan(repo_bare, bare_dir, scan_bare)

        # Full CI: test + lint
        full_dir = tmp_path / "full"
        full_dir.mkdir()
        wf = full_dir / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "ci.yml").write_text("steps:\n  - run: pytest\n  - run: ruff check .\n", encoding="utf-8")
        repo_full = _make_repo("full")
        scan_full = _make_scan(repo_full, full_dir)
        summary_full = self.scanner.scan(repo_full, full_dir, scan_full)

        assert summary_full.score_hint > summary_bare.score_hint

    def test_nonexistent_path_raises(self, tmp_path: Path) -> None:
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path / "missing")

        with pytest.raises(FileNotFoundError):
            self.scanner.scan(repo, tmp_path / "missing", scan)

    def test_only_yaml_files_counted(self, tmp_path: Path) -> None:
        """Non-.yml/.yaml files in .github/workflows should be ignored."""
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("steps:\n  - run: pytest\n", encoding="utf-8")
        (workflows / "README.md").write_text("# workflows", encoding="utf-8")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        self.scanner.scan(repo, tmp_path, scan)

        assert scan.ci.workflow_count == 1


# ---------------------------------------------------------------------------
# DeliveryCleanlinessScanner
# ---------------------------------------------------------------------------


class TestDeliveryCleanlinessScanner:
    scanner = DeliveryCleanlinessScanner()

    def test_clean_repo_has_high_score(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("*.pyc\n__pycache__/\n", encoding="utf-8")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        assert scan.cleanliness.has_gitignore is True
        assert summary.score_hint > 0.8
        assert summary.passed is True

    def test_missing_gitignore_raises_issue(self, tmp_path: Path) -> None:
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        issue_codes = {i.code for i in summary.issues}
        assert "GITIGNORE_MISSING" in issue_codes
        assert scan.cleanliness.has_gitignore is False

    def test_committed_pycache_detected(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "module.cpython-311.pyc").write_bytes(b"fake")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        assert scan.cleanliness.committed_pycache is True
        issue_codes = {i.code for i in summary.issues}
        assert "PYCACHE_COMMITTED" in issue_codes

    def test_committed_virtualenv_detected(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("", encoding="utf-8")
        venv = tmp_path / ".venv"
        venv.mkdir()
        (venv / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        assert scan.cleanliness.committed_virtualenv is True
        issue_codes = {i.code for i in summary.issues}
        assert "VIRTUALENV_COMMITTED" in issue_codes
        assert summary.passed is False  # high severity

    def test_committed_build_artifacts_detected(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("", encoding="utf-8")
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "package-1.0.tar.gz").write_bytes(b"fake")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        assert scan.cleanliness.committed_build_artifacts is True
        issue_codes = {i.code for i in summary.issues}
        assert "BUILD_ARTIFACTS_COMMITTED" in issue_codes

    def test_egg_info_detected(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("", encoding="utf-8")
        egg = tmp_path / "mypackage.egg-info"
        egg.mkdir()
        (egg / "PKG-INFO").write_text("Metadata-Version: 2.1\n", encoding="utf-8")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        assert scan.cleanliness.committed_egg_info is True
        issue_codes = {i.code for i in summary.issues}
        assert "EGG_INFO_COMMITTED" in issue_codes

    def test_oversized_file_detected(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("*.bin\n", encoding="utf-8")
        big = tmp_path / "model.bin"
        big.write_bytes(b"x" * (6 * 1024 * 1024))  # 6 MB > threshold
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        assert len(scan.cleanliness.oversized_files) >= 1
        issue_codes = {i.code for i in summary.issues}
        assert "OVERSIZED_FILES" in issue_codes

    def test_score_drops_with_artifacts(self, tmp_path: Path) -> None:
        # Clean
        clean_dir = tmp_path / "clean"
        clean_dir.mkdir()
        (clean_dir / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        repo_clean = _make_repo("clean")
        scan_clean = _make_scan(repo_clean, clean_dir)
        summary_clean = self.scanner.scan(repo_clean, clean_dir, scan_clean)

        # Dirty
        dirty_dir = tmp_path / "dirty"
        dirty_dir.mkdir()
        pycache = dirty_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "mod.pyc").write_bytes(b"fake")
        venv = dirty_dir / ".venv"
        venv.mkdir()
        (venv / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
        repo_dirty = _make_repo("dirty")
        scan_dirty = _make_scan(repo_dirty, dirty_dir)
        summary_dirty = self.scanner.scan(repo_dirty, dirty_dir, scan_dirty)

        assert summary_clean.score_hint > summary_dirty.score_hint

    def test_nonexistent_path_raises(self, tmp_path: Path) -> None:
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path / "missing")

        with pytest.raises(FileNotFoundError):
            self.scanner.scan(repo, tmp_path / "missing", scan)


# ---------------------------------------------------------------------------
# StructureScanner
# ---------------------------------------------------------------------------


class TestStructureScanner:
    scanner = StructureScanner()

    def test_flat_repo_missing_src_raises_issue(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("print('hi')", encoding="utf-8")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        issue_codes = {i.code for i in summary.issues}
        assert "MAIN_CODE_DIR_MISSING" in issue_codes
        assert scan.structure.has_src_dir is False

    def test_src_dir_detected(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        self.scanner.scan(repo, tmp_path, scan)

        assert scan.structure.has_src_dir is True

    def test_app_dir_accepted_as_alternative(self, tmp_path: Path) -> None:
        (tmp_path / "app").mkdir()
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        assert scan.structure.has_app_dir is True
        issue_codes = {i.code for i in summary.issues}
        assert "MAIN_CODE_DIR_MISSING" not in issue_codes

    def test_tests_dir_detected(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        assert scan.structure.has_tests_dir is True
        issue_codes = {i.code for i in summary.issues}
        assert "TESTS_DIR_MISSING" not in issue_codes

    def test_missing_tests_dir_raises_issue(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        issue_codes = {i.code for i in summary.issues}
        assert "TESTS_DIR_MISSING" in issue_codes

    def test_crowded_root_raises_issue(self, tmp_path: Path) -> None:
        for i in range(25):
            (tmp_path / f"file_{i}.py").write_text("", encoding="utf-8")
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        summary = self.scanner.scan(repo, tmp_path, scan)

        assert scan.structure.root_file_count >= 21
        issue_codes = {i.code for i in summary.issues}
        assert "ROOT_TOO_CROWDED" in issue_codes

    def test_well_structured_layout_detected(self, tmp_path: Path) -> None:
        for d in ("src", "tests", "docs"):
            (tmp_path / d).mkdir()
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        self.scanner.scan(repo, tmp_path, scan)

        assert scan.structure.layout_type == "well_structured"

    def test_structured_layout_detected(self, tmp_path: Path) -> None:
        for d in ("src", "tests"):
            (tmp_path / d).mkdir()
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        self.scanner.scan(repo, tmp_path, scan)

        assert scan.structure.layout_type == "structured"

    def test_score_hint_increases_with_structure(self, tmp_path: Path) -> None:
        # Bare
        bare = tmp_path / "bare"
        bare.mkdir()
        (bare / "main.py").write_text("", encoding="utf-8")
        repo_bare = _make_repo("bare")
        scan_bare = _make_scan(repo_bare, bare)
        summary_bare = self.scanner.scan(repo_bare, bare, scan_bare)

        # Full structure
        full = tmp_path / "full"
        full.mkdir()
        for d in ("src", "tests", "docs"):
            (full / d).mkdir()
        repo_full = _make_repo("full")
        scan_full = _make_scan(repo_full, full)
        summary_full = self.scanner.scan(repo_full, full, scan_full)

        assert summary_full.score_hint > summary_bare.score_hint

    def test_docs_dir_detected(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "docs").mkdir()
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path)

        self.scanner.scan(repo, tmp_path, scan)

        assert scan.structure.has_docs_dir is True

    def test_nonexistent_path_raises(self, tmp_path: Path) -> None:
        repo = _make_repo()
        scan = _make_scan(repo, tmp_path / "missing")

        with pytest.raises(FileNotFoundError):
            self.scanner.scan(repo, tmp_path / "missing", scan)
