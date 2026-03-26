from __future__ import annotations

import json
from pathlib import Path

from portfolio_auditor.fetchers.repo_cache import clones_root
from portfolio_auditor.models.repo_scan import RepoScan
from portfolio_auditor.scanners.ci_scanner import CIScanner
from portfolio_auditor.scanners.delivery_cleanliness_scanner import DeliveryCleanlinessScanner
from portfolio_auditor.scanners.documentation_scanner import DocumentationScanner
from portfolio_auditor.scanners.packaging_scanner import PackagingScanner
from portfolio_auditor.scanners.portfolio_signal_scanner import PortfolioSignalScanner
from portfolio_auditor.scanners.structure_scanner import StructureScanner
from portfolio_auditor.scanners.testing_scanner import TestingScanner
from portfolio_auditor.settings import get_settings


def scan_repository(repo_path: Path) -> RepoScan:
    scan = RepoScan(repo_name=repo_path.name, repo_path=str(repo_path))
    scan.structure = StructureScanner().scan(repo_path)
    scan.documentation = DocumentationScanner().scan(repo_path)
    scan.testing = TestingScanner().scan(repo_path)
    scan.ci = CIScanner().scan(repo_path)
    scan.packaging = PackagingScanner().scan(repo_path)
    scan.cleanliness = DeliveryCleanlinessScanner().scan(repo_path)
    scan.portfolio_signal = PortfolioSignalScanner().scan(repo_path)
    return scan


def scan_all_repositories() -> list[RepoScan]:
    root = clones_root()
    results: list[RepoScan] = []
    out_dir = get_settings().data_dir / "interim" / "scans"
    out_dir.mkdir(parents=True, exist_ok=True)

    for repo_path in sorted(p for p in root.iterdir() if p.is_dir()):
        scan = scan_repository(repo_path)
        results.append(scan)
        (out_dir / f"{repo_path.name}.json").write_text(
            scan.model_dump_json(indent=2), encoding="utf-8"
        )

    return results


def load_scans() -> list[RepoScan]:
    in_dir = get_settings().data_dir / "interim" / "scans"
    if not in_dir.exists():
        return []
    return [RepoScan.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(in_dir.glob("*.json"))]
