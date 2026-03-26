from __future__ import annotations

from pathlib import Path

from portfolio_auditor.models.repo_scan import RepoScanSection
from portfolio_auditor.scanners.base import BaseScanner


class FrontendScanner(BaseScanner):
    section_name = "frontend"

    def scan(self, repo_path: Path) -> RepoScanSection:
        signals = {
            "has_nextjs": (repo_path / "next.config.js").exists() or (repo_path / "next.config.mjs").exists(),
            "has_streamlit": "streamlit" in (repo_path / "requirements.txt").read_text(encoding="utf-8", errors="ignore") if (repo_path / "requirements.txt").exists() else False,
        }
        return RepoScanSection(signals=signals, issues=[])
