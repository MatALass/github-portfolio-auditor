from __future__ import annotations

from pathlib import Path

from portfolio_auditor.models.repo_scan import Issue, RepoScanSection
from portfolio_auditor.scanners.base import BaseScanner


class NotebookScanner(BaseScanner):
    section_name = "notebook"

    def scan(self, repo_path: Path) -> RepoScanSection:
        notebooks = list(repo_path.rglob("*.ipynb"))
        signals = {"notebook_count": len(notebooks)}
        issues = []
        if len(notebooks) > 5:
            issues.append(Issue(code="MANY_NOTEBOOKS", severity="low", message="Many notebooks detected; portfolio signal may be diluted."))
        return RepoScanSection(signals=signals, issues=issues)
