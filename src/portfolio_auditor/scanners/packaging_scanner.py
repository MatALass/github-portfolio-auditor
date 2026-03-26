from __future__ import annotations

from pathlib import Path

from portfolio_auditor.models.repo_scan import Issue, RepoScanSection
from portfolio_auditor.scanners.base import BaseScanner


class PackagingScanner(BaseScanner):
    section_name = "packaging"

    def scan(self, repo_path: Path) -> RepoScanSection:
        signals = {
            "has_pyproject": (repo_path / "pyproject.toml").exists(),
            "has_requirements": (repo_path / "requirements.txt").exists(),
            "has_package_json": (repo_path / "package.json").exists(),
            "has_gitignore": (repo_path / ".gitignore").exists(),
        }
        issues = []
        if not (signals["has_pyproject"] or signals["has_requirements"] or signals["has_package_json"]):
            issues.append(Issue(code="NO_DEPENDENCY_MANIFEST", severity="high", message="No dependency manifest detected."))
        if not signals["has_gitignore"]:
            issues.append(Issue(code="MISSING_GITIGNORE", severity="medium", message=".gitignore is missing."))
        return RepoScanSection(signals=signals, issues=issues)
