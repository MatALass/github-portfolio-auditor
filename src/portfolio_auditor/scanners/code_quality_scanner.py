from __future__ import annotations

from pathlib import Path

from portfolio_auditor.models.repo_scan import RepoScanSection
from portfolio_auditor.scanners.base import BaseScanner


class CodeQualityScanner(BaseScanner):
    section_name = "code_quality"

    def scan(self, repo_path: Path) -> RepoScanSection:
        signals = {
            "has_ruff": "ruff" in (repo_path / "pyproject.toml").read_text(encoding="utf-8", errors="ignore") if (repo_path / "pyproject.toml").exists() else False,
            "has_prettier": (repo_path / ".prettierrc").exists() or (repo_path / ".prettierrc.json").exists(),
        }
        return RepoScanSection(signals=signals, issues=[])
