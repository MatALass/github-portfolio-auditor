from __future__ import annotations

import re
from pathlib import Path

from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_scan import (
    EvidenceItem,
    IssueItem,
    RepoScanResult,
    ScannerSummary,
)
from portfolio_auditor.scanners.base import BaseScanner


class DocumentationScanner(BaseScanner):
    scanner_name = "documentation"

    README_CANDIDATES = (
        "README.md",
        "README.rst",
        "README.txt",
        "readme.md",
        "readme.rst",
        "readme.txt",
    )

    LICENSE_CANDIDATES = (
        "LICENSE",
        "LICENSE.txt",
        "LICENSE.md",
        "license",
        "license.txt",
        "license.md",
    )

    ENV_EXAMPLE_CANDIDATES = (
        ".env.example",
        ".env.sample",
        ".env.template",
        "env.example",
    )

    ASSET_DIR_CANDIDATES = (
        "assets",
        "images",
        "screenshots",
        "docs/assets",
        "public",
    )

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

        readme_path = self._find_first_existing(local_path, self.README_CANDIDATES)
        license_path = self._find_first_existing(local_path, self.LICENSE_CANDIDATES)
        env_example_path = self._find_first_existing(local_path, self.ENV_EXAMPLE_CANDIDATES)

        has_assets = any((local_path / candidate).exists() for candidate in self.ASSET_DIR_CANDIDATES)

        has_readme = readme_path is not None
        readme_text = self.safe_read_text(readme_path) if readme_path else ""
        readme_word_count = len(readme_text.split()) if readme_text else 0

        has_installation = self._contains_section(readme_text, ["install", "installation", "setup"])
        has_usage = self._contains_section(readme_text, ["usage", "how to run", "run", "quick start"])
        has_architecture = self._contains_section(
            readme_text,
            ["architecture", "project structure", "structure", "design"],
        )
        has_results = self._contains_section(readme_text, ["results", "output", "demo", "features"])
        has_roadmap = self._contains_section(readme_text, ["roadmap", "next steps", "future work"])

        scan_result.documentation.has_readme = has_readme
        scan_result.documentation.readme_path = (
            str(readme_path.relative_to(local_path)) if readme_path else None
        )
        scan_result.documentation.readme_word_count = readme_word_count
        scan_result.documentation.has_installation_section = has_installation
        scan_result.documentation.has_usage_section = has_usage
        scan_result.documentation.has_architecture_section = has_architecture
        scan_result.documentation.has_results_section = has_results
        scan_result.documentation.has_roadmap_section = has_roadmap
        scan_result.documentation.has_license_file = license_path is not None
        scan_result.documentation.has_env_example = env_example_path is not None
        scan_result.documentation.has_screenshots_or_assets = has_assets

        metrics["has_readme"] = has_readme
        metrics["readme_word_count"] = readme_word_count
        metrics["has_installation_section"] = has_installation
        metrics["has_usage_section"] = has_usage
        metrics["has_architecture_section"] = has_architecture
        metrics["has_results_section"] = has_results
        metrics["has_roadmap_section"] = has_roadmap
        metrics["has_license_file"] = license_path is not None
        metrics["has_env_example"] = env_example_path is not None
        metrics["has_screenshots_or_assets"] = has_assets

        if has_readme:
            evidence.append(
                EvidenceItem(
                    source=self.scanner_name,
                    message=f"README detected with approximately {readme_word_count} words.",
                    path=str(readme_path.relative_to(local_path)),
                    value=readme_word_count,
                )
            )
        else:
            issues.append(
                IssueItem(
                    code="README_MISSING",
                    title="README missing",
                    description="The repository does not contain a README file.",
                    severity="high",
                    scanner=self.scanner_name,
                    recommendation="Add a complete README describing purpose, setup, usage, and outcomes.",
                )
            )

        if has_readme and readme_word_count < 120:
            issues.append(
                IssueItem(
                    code="README_TOO_SHORT",
                    title="README too short",
                    description=(
                        "The README exists but appears too short to explain the project clearly "
                        "to a recruiter or manager."
                    ),
                    severity="medium",
                    scanner=self.scanner_name,
                    recommendation="Expand the README with project context, setup, usage, and architecture.",
                )
            )

        if has_readme and not has_installation:
            issues.append(
                IssueItem(
                    code="INSTALLATION_INSTRUCTIONS_MISSING",
                    title="Installation instructions missing",
                    description="The README does not clearly explain how to install or set up the project.",
                    severity="medium",
                    scanner=self.scanner_name,
                    recommendation="Add an installation or setup section with concrete commands.",
                )
            )

        if has_readme and not has_usage:
            issues.append(
                IssueItem(
                    code="USAGE_INSTRUCTIONS_MISSING",
                    title="Usage instructions missing",
                    description="The README does not clearly explain how to run or use the project.",
                    severity="medium",
                    scanner=self.scanner_name,
                    recommendation="Add a usage section with examples and expected outputs.",
                )
            )

        if has_readme and not has_architecture:
            issues.append(
                IssueItem(
                    code="ARCHITECTURE_SECTION_MISSING",
                    title="Architecture or structure section missing",
                    description=(
                        "The README does not explain the project structure or architecture, which "
                        "reduces maintainability signal."
                    ),
                    severity="low",
                    scanner=self.scanner_name,
                    recommendation="Add a short section describing the project structure and main modules.",
                )
            )

        if license_path is None:
            issues.append(
                IssueItem(
                    code="LICENSE_MISSING",
                    title="License file missing",
                    description="The repository does not include a license file.",
                    severity="low",
                    scanner=self.scanner_name,
                    recommendation="Add a LICENSE file if the repository is intended to be public and reusable.",
                )
            )
        else:
            evidence.append(
                EvidenceItem(
                    source=self.scanner_name,
                    message="License file detected.",
                    path=str(license_path.relative_to(local_path)),
                    value=True,
                )
            )

        if env_example_path is not None:
            evidence.append(
                EvidenceItem(
                    source=self.scanner_name,
                    message="Environment example file detected.",
                    path=str(env_example_path.relative_to(local_path)),
                    value=True,
                )
            )

        if has_assets:
            evidence.append(
                EvidenceItem(
                    source=self.scanner_name,
                    message="Documentation assets or screenshots directory detected.",
                    value=True,
                )
            )

        if has_installation:
            scan_result.documentation.notes.append("Installation guidance detected.")
        if has_usage:
            scan_result.documentation.notes.append("Usage guidance detected.")
        if has_architecture:
            scan_result.documentation.notes.append("Architecture or structure guidance detected.")
        if has_results:
            scan_result.documentation.notes.append("Results/demo/features section detected.")
        if has_roadmap:
            scan_result.documentation.notes.append("Roadmap or future work section detected.")

        for item in evidence:
            scan_result.add_evidence(item)
        for item in issues:
            scan_result.add_issue(item)

        passed = not any(issue.severity in {"high", "critical"} for issue in issues)
        score_hint = self._compute_score_hint(
            has_readme=has_readme,
            readme_word_count=readme_word_count,
            has_installation=has_installation,
            has_usage=has_usage,
            has_architecture=has_architecture,
            has_results=has_results,
            has_license=license_path is not None,
            has_env_example=env_example_path is not None,
            has_assets=has_assets,
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
    def _find_first_existing(root: Path, candidates: tuple[str, ...]) -> Path | None:
        for candidate in candidates:
            path = root / candidate
            if path.exists() and path.is_file():
                return path
        return None

    @staticmethod
    def _contains_section(text: str, keywords: list[str]) -> bool:
        if not text:
            return False

        lowered = text.lower()
        for keyword in keywords:
            escaped = re.escape(keyword.lower())
            patterns = [
                rf"^#+\s+.*{escaped}.*$",
                rf"^\*\*.*{escaped}.*\*\*$",
                rf"\b{escaped}\b",
            ]
            for pattern in patterns:
                if re.search(pattern, lowered, flags=re.MULTILINE):
                    return True
        return False

    @staticmethod
    def _compute_score_hint(
        *,
        has_readme: bool,
        readme_word_count: int,
        has_installation: bool,
        has_usage: bool,
        has_architecture: bool,
        has_results: bool,
        has_license: bool,
        has_env_example: bool,
        has_assets: bool,
    ) -> float:
        score = 0.0
        if has_readme:
            score += 0.3
        if readme_word_count >= 200:
            score += 0.15
        elif readme_word_count >= 120:
            score += 0.1
        if has_installation:
            score += 0.15
        if has_usage:
            score += 0.15
        if has_architecture:
            score += 0.1
        if has_results:
            score += 0.05
        if has_license:
            score += 0.05
        if has_env_example:
            score += 0.03
        if has_assets:
            score += 0.02
        return min(1.0, round(score, 2))