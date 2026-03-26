from __future__ import annotations

from pathlib import Path

from portfolio_auditor.models.repo_scan import Issue, RepoScanSection
from portfolio_auditor.scanners.base import BaseScanner


class PortfolioSignalScanner(BaseScanner):
    section_name = "portfolio_signal"

    def scan(self, repo_path: Path) -> RepoScanSection:
        name = repo_path.name.lower()
        readme = repo_path / "README.md"
        readme_text = readme.read_text(encoding="utf-8", errors="ignore").lower() if readme.exists() else ""

        signals = {
            "has_demo_language": any(word in readme_text for word in ["demo", "dashboard", "cli", "model", "pipeline", "architecture"]),
            "name_quality": "weak" if name in {"test", "demo", "project"} else "ok",
        }
        issues = []
        if signals["name_quality"] == "weak":
            issues.append(Issue(code="WEAK_REPO_NAME", severity="medium", message="Repository name is too generic for strong portfolio signaling."))
        return RepoScanSection(signals=signals, issues=issues)
