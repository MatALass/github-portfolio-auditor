from __future__ import annotations

from pathlib import Path

from portfolio_auditor.models.repo_scan import RepoScanSection
from portfolio_auditor.scanners.base import BaseScanner


class SecurityHygieneScanner(BaseScanner):
    section_name = "security_hygiene"

    def scan(self, repo_path: Path) -> RepoScanSection:
        signals = {
            "has_env_example": (repo_path / ".env.example").exists(),
            "has_dotenv": (repo_path / ".env").exists(),
        }
        return RepoScanSection(signals=signals, issues=[])
