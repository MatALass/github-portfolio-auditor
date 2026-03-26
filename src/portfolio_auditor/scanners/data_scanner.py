from __future__ import annotations

from pathlib import Path

from portfolio_auditor.models.repo_scan import RepoScanSection
from portfolio_auditor.scanners.base import BaseScanner


class DataScanner(BaseScanner):
    section_name = "data"

    def scan(self, repo_path: Path) -> RepoScanSection:
        data_dir = repo_path / "data"
        signals = {
            "has_data_dir": data_dir.exists(),
            "has_raw": (data_dir / "raw").exists(),
            "has_interim": (data_dir / "interim").exists(),
            "has_processed": (data_dir / "processed").exists(),
        }
        return RepoScanSection(signals=signals, issues=[])
