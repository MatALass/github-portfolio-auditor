from __future__ import annotations

from pathlib import Path

from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_scan import (
    EvidenceItem,
    IssueItem,
    RepoScanResult,
    ScannerSummary,
)
from portfolio_auditor.scanners.base import BaseScanner


class DeliveryCleanlinessScanner(BaseScanner):
    scanner_name = "delivery_cleanliness"

    BUILD_ARTIFACT_DIRS = {
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        "htmlcov",
        "coverage",
        ".coverage",
    }

    EGG_INFO_SUFFIX = ".egg-info"
    LARGE_FILE_THRESHOLD_BYTES = 5 * 1024 * 1024

    def scan(
        self,
        repo: RepoMetadata,
        local_path: Path,
        scan_result: RepoScanResult,
    ) -> ScannerSummary:
        self.ensure_repo_exists(local_path)

        evidence: list[EvidenceItem] = []
        issues: list[IssueItem] = []
        metrics: dict[str, int | float | str | bool | None] = {}

        has_gitignore = (local_path / ".gitignore").exists()

        committed_virtualenv = any(
            (local_path / candidate).exists()
            for candidate in (".venv", "venv", "env", ".env")
            if (local_path / candidate).is_dir()
        )

        committed_pycache = any(path.is_dir() and path.name == "__pycache__" for path in local_path.rglob("__pycache__"))
        committed_pytest_cache = any(
            path.is_dir() and path.name == ".pytest_cache" for path in local_path.rglob(".pytest_cache")
        )

        committed_build_artifacts = any(
            path.name in self.BUILD_ARTIFACT_DIRS for path in local_path.rglob("*") if path.exists()
        )

        committed_egg_info = any(
            path.name.endswith(self.EGG_INFO_SUFFIX) for path in local_path.rglob("*") if path.exists()
        )

        oversized_files = sorted(
            [
                str(path.relative_to(local_path))
                for path in local_path.rglob("*")
                if path.is_file() and path.stat().st_size >= self.LARGE_FILE_THRESHOLD_BYTES
            ]
        )

        suspicious_generated_files = sorted(
            [
                str(path.relative_to(local_path))
                for path in local_path.rglob("*")
                if path.is_file()
                and (
                    path.suffix.lower() in {".coverage", ".log", ".tmp"}
                    or path.name.lower() in {"coverage.xml", "pytestdebug.log"}
                )
            ]
        )

        scan_result.cleanliness.has_gitignore = has_gitignore
        scan_result.cleanliness.committed_virtualenv = committed_virtualenv
        scan_result.cleanliness.committed_pycache = committed_pycache
        scan_result.cleanliness.committed_pytest_cache = committed_pytest_cache
        scan_result.cleanliness.committed_build_artifacts = committed_build_artifacts
        scan_result.cleanliness.committed_egg_info = committed_egg_info
        scan_result.cleanliness.oversized_files = oversized_files
        scan_result.cleanliness.suspicious_generated_files = suspicious_generated_files

        metrics["has_gitignore"] = has_gitignore
        metrics["committed_virtualenv"] = committed_virtualenv
        metrics["committed_pycache"] = committed_pycache
        metrics["committed_pytest_cache"] = committed_pytest_cache
        metrics["committed_build_artifacts"] = committed_build_artifacts
        metrics["committed_egg_info"] = committed_egg_info
        metrics["oversized_file_count"] = len(oversized_files)
        metrics["suspicious_generated_file_count"] = len(suspicious_generated_files)

        if has_gitignore:
            evidence.append(
                EvidenceItem(
                    source=self.scanner_name,
                    message=".gitignore file detected.",
                    path=".gitignore",
                    value=True,
                )
            )
        else:
            issues.append(
                IssueItem(
                    code="GITIGNORE_MISSING",
                    title=".gitignore missing",
                    description="The repository does not contain a .gitignore file.",
                    severity="medium",
                    scanner=self.scanner_name,
                    recommendation="Add a proper .gitignore to avoid committing local or generated artifacts.",
                )
            )

        if committed_virtualenv:
            issues.append(
                IssueItem(
                    code="VIRTUALENV_COMMITTED",
                    title="Virtual environment committed",
                    description="A local virtual environment directory appears to be committed.",
                    severity="high",
                    scanner=self.scanner_name,
                    recommendation="Remove the virtual environment from version control and ignore it in .gitignore.",
                )
            )

        if committed_pycache:
            issues.append(
                IssueItem(
                    code="PYCACHE_COMMITTED",
                    title="__pycache__ committed",
                    description="Python bytecode cache directories were detected in the repository.",
                    severity="medium",
                    scanner=self.scanner_name,
                    recommendation="Delete __pycache__ directories and ignore them in .gitignore.",
                )
            )

        if committed_pytest_cache:
            issues.append(
                IssueItem(
                    code="PYTEST_CACHE_COMMITTED",
                    title=".pytest_cache committed",
                    description="Pytest cache files were detected in version control.",
                    severity="low",
                    scanner=self.scanner_name,
                    recommendation="Delete .pytest_cache and ignore it in .gitignore.",
                )
            )

        if committed_build_artifacts:
            issues.append(
                IssueItem(
                    code="BUILD_ARTIFACTS_COMMITTED",
                    title="Build or cache artifacts committed",
                    description="Generated build or cache artifacts were detected in the repository.",
                    severity="medium",
                    scanner=self.scanner_name,
                    recommendation="Remove generated artifacts such as dist/, build/, htmlcov/, or cache folders.",
                )
            )

        if committed_egg_info:
            issues.append(
                IssueItem(
                    code="EGG_INFO_COMMITTED",
                    title=".egg-info committed",
                    description="Python packaging metadata directories were detected in the repository.",
                    severity="low",
                    scanner=self.scanner_name,
                    recommendation="Remove *.egg-info from version control and ignore them.",
                )
            )

        if oversized_files:
            issues.append(
                IssueItem(
                    code="OVERSIZED_FILES",
                    title="Oversized files detected",
                    description=(
                        "The repository contains very large files that may hurt delivery quality, "
                        "clone speed, and portfolio cleanliness."
                    ),
                    severity="low",
                    scanner=self.scanner_name,
                    recommendation="Remove unnecessary large files or move them to external storage if appropriate.",
                )
            )
            evidence.append(
                EvidenceItem(
                    source=self.scanner_name,
                    message=f"Detected {len(oversized_files)} file(s) larger than {self.LARGE_FILE_THRESHOLD_BYTES} bytes.",
                    value=len(oversized_files),
                )
            )

        if suspicious_generated_files:
            issues.append(
                IssueItem(
                    code="GENERATED_FILES_COMMITTED",
                    title="Generated files detected",
                    description="Generated or temporary files appear to be committed.",
                    severity="low",
                    scanner=self.scanner_name,
                    recommendation="Remove generated files and extend .gitignore if needed.",
                )
            )

        if has_gitignore:
            scan_result.cleanliness.notes.append(".gitignore detected.")
        if not any(
            [
                committed_virtualenv,
                committed_pycache,
                committed_pytest_cache,
                committed_build_artifacts,
                committed_egg_info,
            ]
        ):
            scan_result.cleanliness.notes.append("No major Python build/cache artifacts detected.")

        for item in evidence:
            scan_result.add_evidence(item)
        for item in issues:
            scan_result.add_issue(item)

        passed = not any(issue.severity in {"high", "critical"} for issue in issues)
        score_hint = self._compute_score_hint(
            has_gitignore=has_gitignore,
            committed_virtualenv=committed_virtualenv,
            committed_pycache=committed_pycache,
            committed_pytest_cache=committed_pytest_cache,
            committed_build_artifacts=committed_build_artifacts,
            committed_egg_info=committed_egg_info,
            oversized_file_count=len(oversized_files),
            suspicious_generated_file_count=len(suspicious_generated_files),
        )

        return ScannerSummary(
            scanner_name=self.scanner_name,
            passed=passed,
            score_hint=score_hint,
            evidence=evidence,
            issues=issues,
            metrics=metrics,
        )

    @staticmethod
    def _compute_score_hint(
        *,
        has_gitignore: bool,
        committed_virtualenv: bool,
        committed_pycache: bool,
        committed_pytest_cache: bool,
        committed_build_artifacts: bool,
        committed_egg_info: bool,
        oversized_file_count: int,
        suspicious_generated_file_count: int,
    ) -> float:
        score = 0.0

        if has_gitignore:
            score += 0.35
        else:
            score += 0.0

        penalties = 0.0
        if committed_virtualenv:
            penalties += 0.35
        if committed_pycache:
            penalties += 0.15
        if committed_pytest_cache:
            penalties += 0.05
        if committed_build_artifacts:
            penalties += 0.15
        if committed_egg_info:
            penalties += 0.05
        if oversized_file_count > 0:
            penalties += min(0.15, oversized_file_count * 0.02)
        if suspicious_generated_file_count > 0:
            penalties += min(0.1, suspicious_generated_file_count * 0.02)

        base_bonus = 0.65
        final_score = base_bonus + score - penalties
        return max(0.0, min(1.0, round(final_score, 2)))