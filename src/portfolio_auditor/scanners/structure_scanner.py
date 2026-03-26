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


class StructureScanner(BaseScanner):
    scanner_name = "structure"

    ROOT_FILE_HEAVY_THRESHOLD = 20

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

        root_entries = list(local_path.iterdir())
        root_files = [entry for entry in root_entries if entry.is_file()]
        root_dirs = [entry for entry in root_entries if entry.is_dir()]

        has_src_dir = (local_path / "src").is_dir()
        has_app_dir = (local_path / "app").is_dir()
        has_tests_dir = (local_path / "tests").is_dir()
        has_docs_dir = (local_path / "docs").is_dir()
        has_data_dir = (local_path / "data").is_dir()
        has_scripts_dir = (local_path / "scripts").is_dir()

        large_root_files = sorted(
            [
                file.name
                for file in root_files
                if file.stat().st_size > 200_000
            ]
        )

        layout_type = self._detect_layout_type(
            has_src_dir=has_src_dir,
            has_app_dir=has_app_dir,
            has_tests_dir=has_tests_dir,
            has_docs_dir=has_docs_dir,
            root_files=root_files,
            root_dirs=root_dirs,
        )

        scan_result.structure.has_src_dir = has_src_dir
        scan_result.structure.has_app_dir = has_app_dir
        scan_result.structure.has_tests_dir = has_tests_dir
        scan_result.structure.has_docs_dir = has_docs_dir
        scan_result.structure.has_data_dir = has_data_dir
        scan_result.structure.has_scripts_dir = has_scripts_dir
        scan_result.structure.root_file_count = len(root_files)
        scan_result.structure.large_root_files = large_root_files
        scan_result.structure.layout_type = layout_type

        metrics["has_src_dir"] = has_src_dir
        metrics["has_app_dir"] = has_app_dir
        metrics["has_tests_dir"] = has_tests_dir
        metrics["has_docs_dir"] = has_docs_dir
        metrics["has_data_dir"] = has_data_dir
        metrics["has_scripts_dir"] = has_scripts_dir
        metrics["root_file_count"] = len(root_files)
        metrics["root_dir_count"] = len(root_dirs)
        metrics["layout_type"] = layout_type
        metrics["large_root_file_count"] = len(large_root_files)

        evidence.append(
            EvidenceItem(
                source=self.scanner_name,
                message=f"Detected layout type: {layout_type}",
                value=layout_type,
            )
        )

        if has_src_dir:
            evidence.append(
                EvidenceItem(
                    source=self.scanner_name,
                    message="Repository uses a dedicated src/ directory.",
                    path="src",
                    value=True,
                )
            )

        if has_tests_dir:
            evidence.append(
                EvidenceItem(
                    source=self.scanner_name,
                    message="Repository contains a tests/ directory.",
                    path="tests",
                    value=True,
                )
            )

        if not has_src_dir and not has_app_dir:
            issues.append(
                IssueItem(
                    code="MAIN_CODE_DIR_MISSING",
                    title="Dedicated main code directory missing",
                    description=(
                        "The repository does not expose a clear main application directory "
                        "such as src/ or app/."
                    ),
                    severity="medium",
                    scanner=self.scanner_name,
                    recommendation="Introduce a dedicated source directory to improve structure clarity.",
                )
            )

        if not has_tests_dir:
            issues.append(
                IssueItem(
                    code="TESTS_DIR_MISSING",
                    title="Tests directory missing",
                    description="The repository does not include a top-level tests/ directory.",
                    severity="medium",
                    scanner=self.scanner_name,
                    recommendation="Add a tests/ directory and start building a core test suite.",
                )
            )

        if len(root_files) > self.ROOT_FILE_HEAVY_THRESHOLD:
            issues.append(
                IssueItem(
                    code="ROOT_TOO_CROWDED",
                    title="Repository root is overcrowded",
                    description=(
                        f"The repository root contains {len(root_files)} files, which suggests "
                        "a cluttered structure and weak organization."
                    ),
                    severity="medium",
                    scanner=self.scanner_name,
                    recommendation="Group files into dedicated folders such as src/, docs/, scripts/, and tests/.",
                )
            )

        if large_root_files:
            issues.append(
                IssueItem(
                    code="LARGE_ROOT_FILES",
                    title="Large files present in repository root",
                    description=(
                        "The repository root contains large files that reduce delivery clarity "
                        "and may indicate generated or misplaced artifacts."
                    ),
                    severity="low",
                    scanner=self.scanner_name,
                    recommendation="Move heavy assets to dedicated folders or remove non-essential generated files.",
                )
            )

        if has_docs_dir:
            scan_result.structure.notes.append("docs/ directory detected.")
        if has_scripts_dir:
            scan_result.structure.notes.append("scripts/ directory detected.")
        if layout_type:
            scan_result.structure.notes.append(f"Layout classified as {layout_type}.")

        for item in evidence:
            scan_result.add_evidence(item)
        for item in issues:
            scan_result.add_issue(item)

        passed = len([issue for issue in issues if issue.severity in {"high", "critical"}]) == 0
        score_hint = self._compute_score_hint(
            has_src_dir=has_src_dir,
            has_app_dir=has_app_dir,
            has_tests_dir=has_tests_dir,
            has_docs_dir=has_docs_dir,
            root_file_count=len(root_files),
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
    def _detect_layout_type(
        *,
        has_src_dir: bool,
        has_app_dir: bool,
        has_tests_dir: bool,
        has_docs_dir: bool,
        root_files: list[Path],
        root_dirs: list[Path],
    ) -> str:
        if has_src_dir and has_tests_dir and has_docs_dir:
            return "well_structured"
        if has_src_dir and has_tests_dir:
            return "structured"
        if has_app_dir and has_tests_dir:
            return "app_with_tests"
        if has_src_dir or has_app_dir:
            return "partially_structured"
        if len(root_dirs) <= 2 and len(root_files) >= 8:
            return "flat"
        return "basic"

    @staticmethod
    def _compute_score_hint(
        *,
        has_src_dir: bool,
        has_app_dir: bool,
        has_tests_dir: bool,
        has_docs_dir: bool,
        root_file_count: int,
    ) -> float:
        score = 0.2
        if has_src_dir:
            score += 0.3
        elif has_app_dir:
            score += 0.2

        if has_tests_dir:
            score += 0.2
        if has_docs_dir:
            score += 0.15
        if root_file_count <= 10:
            score += 0.15

        return min(1.0, round(score, 2))