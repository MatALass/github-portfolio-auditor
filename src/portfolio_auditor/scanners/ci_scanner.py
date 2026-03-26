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


class CiScanner(BaseScanner):
    scanner_name = "ci"

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

        workflows_dir = local_path / ".github" / "workflows"
        workflow_files = []
        if workflows_dir.exists() and workflows_dir.is_dir():
            workflow_files = sorted(
                [
                    str(path.relative_to(local_path))
                    for path in workflows_dir.glob("*")
                    if path.is_file() and path.suffix in {".yml", ".yaml"}
                ]
            )

        workflow_contents = {
            rel_path: self.safe_read_text(local_path / rel_path).lower()
            for rel_path in workflow_files
        }

        has_github_actions = bool(workflow_files)
        has_test_workflow = any(
            self._looks_like_test_workflow(content) for content in workflow_contents.values()
        )
        has_lint_workflow = any(
            self._looks_like_lint_workflow(content) for content in workflow_contents.values()
        )
        has_build_workflow = any(
            self._looks_like_build_workflow(content) for content in workflow_contents.values()
        )

        scan_result.ci.has_github_actions = has_github_actions
        scan_result.ci.workflow_count = len(workflow_files)
        scan_result.ci.workflow_files = workflow_files
        scan_result.ci.has_test_workflow = has_test_workflow
        scan_result.ci.has_lint_workflow = has_lint_workflow
        scan_result.ci.has_build_workflow = has_build_workflow

        metrics["has_github_actions"] = has_github_actions
        metrics["workflow_count"] = len(workflow_files)
        metrics["has_test_workflow"] = has_test_workflow
        metrics["has_lint_workflow"] = has_lint_workflow
        metrics["has_build_workflow"] = has_build_workflow

        if has_github_actions:
            evidence.append(
                EvidenceItem(
                    source=self.scanner_name,
                    message=f"Detected {len(workflow_files)} GitHub Actions workflow file(s).",
                    path=".github/workflows",
                    value=len(workflow_files),
                )
            )
        else:
            issues.append(
                IssueItem(
                    code="CI_MISSING",
                    title="CI workflow missing",
                    description="No GitHub Actions workflows were detected.",
                    severity="medium",
                    scanner=self.scanner_name,
                    recommendation="Add a CI workflow to run tests, linting, or build checks automatically.",
                )
            )

        if has_github_actions and not has_test_workflow:
            issues.append(
                IssueItem(
                    code="CI_TESTS_NOT_DETECTED",
                    title="No test workflow detected in CI",
                    description=(
                        "GitHub Actions is present, but no workflow clearly appears to run automated tests."
                    ),
                    severity="medium",
                    scanner=self.scanner_name,
                    recommendation="Add or clarify a workflow step that runs the automated test suite.",
                )
            )

        if has_github_actions and has_test_workflow:
            evidence.append(
                EvidenceItem(
                    source=self.scanner_name,
                    message="Detected a workflow that appears to run tests.",
                    value=True,
                )
            )

        if has_github_actions and has_lint_workflow:
            evidence.append(
                EvidenceItem(
                    source=self.scanner_name,
                    message="Detected linting or code quality checks in CI.",
                    value=True,
                )
            )

        if has_github_actions and has_build_workflow:
            evidence.append(
                EvidenceItem(
                    source=self.scanner_name,
                    message="Detected build or validation steps in CI.",
                    value=True,
                )
            )

        if has_github_actions and not has_lint_workflow:
            issues.append(
                IssueItem(
                    code="CI_LINT_NOT_DETECTED",
                    title="No lint workflow detected in CI",
                    description=(
                        "GitHub Actions is present, but no workflow clearly appears to run linting or static checks."
                    ),
                    severity="low",
                    scanner=self.scanner_name,
                    recommendation="Add linting or static validation checks to improve delivery quality.",
                )
            )

        if has_test_workflow:
            scan_result.ci.notes.append("Test workflow detected.")
        if has_lint_workflow:
            scan_result.ci.notes.append("Lint workflow detected.")
        if has_build_workflow:
            scan_result.ci.notes.append("Build workflow detected.")

        for item in evidence:
            scan_result.add_evidence(item)
        for item in issues:
            scan_result.add_issue(item)

        passed = not any(issue.severity in {"high", "critical"} for issue in issues)
        score_hint = self._compute_score_hint(
            has_github_actions=has_github_actions,
            has_test_workflow=has_test_workflow,
            has_lint_workflow=has_lint_workflow,
            has_build_workflow=has_build_workflow,
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
    def _looks_like_test_workflow(content: str) -> bool:
        keywords = [
            "pytest",
            "unittest",
            "jest",
            "vitest",
            "npm test",
            "pnpm test",
            "yarn test",
            "go test",
            "cargo test",
            "mvn test",
        ]
        return any(keyword in content for keyword in keywords)

    @staticmethod
    def _looks_like_lint_workflow(content: str) -> bool:
        keywords = [
            "ruff",
            "flake8",
            "pylint",
            "eslint",
            "prettier",
            "black --check",
            "mypy",
            "tsc",
        ]
        return any(keyword in content for keyword in keywords)

    @staticmethod
    def _looks_like_build_workflow(content: str) -> bool:
        keywords = [
            "npm run build",
            "pnpm build",
            "yarn build",
            "python -m build",
            "docker build",
            "mkdocs build",
            "streamlit",
        ]
        return any(keyword in content for keyword in keywords)

    @staticmethod
    def _compute_score_hint(
        *,
        has_github_actions: bool,
        has_test_workflow: bool,
        has_lint_workflow: bool,
        has_build_workflow: bool,
    ) -> float:
        if not has_github_actions:
            return 0.0

        score = 0.4
        if has_test_workflow:
            score += 0.3
        if has_lint_workflow:
            score += 0.2
        if has_build_workflow:
            score += 0.1

        return min(1.0, round(score, 2))