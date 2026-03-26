from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_scan import RepoScanResult, ScannerSummary


class BaseScanner(ABC):
    """
    Base class for all scanners.

    Each scanner is responsible for:
    - inspecting a local repository path
    - updating the RepoScanResult in-place
    - returning a ScannerSummary
    """

    scanner_name: str = "base"

    @abstractmethod
    def scan(
        self,
        repo: RepoMetadata,
        local_path: Path,
        scan_result: RepoScanResult,
    ) -> ScannerSummary:
        raise NotImplementedError

    def ensure_repo_exists(self, local_path: Path) -> None:
        if not local_path.exists():
            raise FileNotFoundError(f"Repository path does not exist: {local_path}")
        if not local_path.is_dir():
            raise NotADirectoryError(f"Repository path is not a directory: {local_path}")

    def iter_relative_paths(self, root: Path) -> list[Path]:
        """
        Return all paths relative to the repository root.
        """
        return [path.relative_to(root) for path in root.rglob("*")]

    def safe_read_text(
        self,
        path: Path,
        *,
        max_chars: int = 200_000,
    ) -> str:
        """
        Best-effort text reader with UTF-8 fallback behavior.
        """
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                text = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                try:
                    text = path.read_text(encoding="latin-1")
                except UnicodeDecodeError:
                    return ""
        return text[:max_chars]