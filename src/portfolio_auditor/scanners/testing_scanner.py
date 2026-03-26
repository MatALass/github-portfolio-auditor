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


class TestingScanner(BaseScanner):
    scanner_name = "testing"

    TEST_DIR_CANDIDATES = ("tests", "test", "__tests__", "spec")
    PYTEST_CONFIG_CANDIDATES = ("pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg")
    JEST_CONFIG_CANDIDATES = (
        "jest.config.js",
        "jest.config.cjs",
        "jest.config.ts",
        "package.json",
    )
    VITEST_CONFIG_CANDIDATES = (
        "vitest.config.ts",
        "vitest.config.js",
        "package.json",
    )
    COVERAGE_CONFIG_CANDIDATES = (
        ".coveragerc",
        "pyproject.toml",
        "setup.cfg",
        "tox.ini",
        "package.json",
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

        test_directories = self._find_test_directories(local_path)
        test_files = self._find_test_files(local_path)
        detected_frameworks = self._detect_frameworks(local_path)

        has_pytest_config = self._has_pytest_config(local_path)
        has_jest_config = self._has_jest_config(local_path)
        has_vitest_config = self._has_vitest_config(local_path)
        has_coverage_config = self._has_coverage_config(local_path)

        has_tests = bool(test_directories or test_files)

        scan_result.testing.has_tests = has_tests
        scan_result.testing.test_file_count = len(test_files)
        scan_result.testing.test_directories = sorted(test_directories)
        scan_result.testing.detected_frameworks = detected_frameworks
        scan_result.testing.has_pytest_config = has_pytest_config
        scan_result.testing.has_jest_config = has_jest_config
        scan_result.testing.has_vitest_config = has_vitest_config
        scan_result.testing.has_coverage_config = has_coverage_config

        metrics["has_tests"] = has_tests
        metrics["test_directory_count"] = len(test_directories)
        metrics["test_file_count"] = len(test_files)
        metrics["detected_framework_count"] = len(detected_frameworks)
        metrics["has_pytest_config"] = has_pytest_config
        metrics["has_jest_config"] = has_jest_config
        metrics["has_vitest_config"] = has_vitest_config
        metrics["has_coverage_config"] = has_coverage_config

        if has_tests:
            evidence.append(
                EvidenceItem(
                    source=self.scanner_name,
                    message=f"Detected {len(test_files)} test files across {len(test_directories)} test directories.",
                    value=len(test_files),
                )
            )
        else:
            issues.append(
                IssueItem(
                    code="NO_TESTS_DETECTED",
                    title="No tests detected",
                    description="The repository does not appear to contain an automated test suite.",
                    severity="high",
                    scanner=self.scanner_name,
                    recommendation="Add a core automated test suite for the most important business logic.",
                )
            )

        if has_tests and len(test_files) < 3:
            issues.append(
                IssueItem(
                    code="WEAK_TEST_BASELINE",
                    title="Weak test baseline",
                    description=(
                        "Tests exist, but the detected test footprint is very small and may not provide "
                        "meaningful confidence."
                    ),
                    severity="medium",
                    scanner=self.scanner_name,
                    recommendation="Expand the test suite to cover core business logic and edge cases.",
                )
            )

        if detected_frameworks:
            evidence.append(
                EvidenceItem(
                    source=self.scanner_name,
                    message=f"Detected testing frameworks: {', '.join(detected_frameworks)}.",
                    value=", ".join(detected_frameworks),
                )
            )

        if has_coverage_config:
            evidence.append(
                EvidenceItem(
                    source=self.scanner_name,
                    message="Coverage-related configuration detected.",
                    value=True,
                )
            )

        if has_tests and not detected_frameworks:
            issues.append(
                IssueItem(
                    code="TEST_FRAMEWORK_UNCLEAR",
                    title="Testing framework unclear",
                    description=(
                        "Test-like files exist, but the repository does not expose a clearly configured "
                        "testing framework."
                    ),
                    severity="low",
                    scanner=self.scanner_name,
                    recommendation="Make the test runner explicit through configuration or documentation.",
                )
            )

        if has_tests and not has_coverage_config:
            issues.append(
                IssueItem(
                    code="COVERAGE_CONFIG_MISSING",
                    title="Coverage configuration missing",
                    description=(
                        "Tests appear to exist, but no coverage-related configuration was detected."
                    ),
                    severity="low",
                    scanner=self.scanner_name,
                    recommendation="Add basic coverage support to improve reliability signal.",
                )
            )

        if has_pytest_config:
            scan_result.testing.notes.append("Pytest configuration detected.")
        if has_jest_config:
            scan_result.testing.notes.append("Jest configuration detected.")
        if has_vitest_config:
            scan_result.testing.notes.append("Vitest configuration detected.")
        if has_coverage_config:
            scan_result.testing.notes.append("Coverage-related configuration detected.")

        for item in evidence:
            scan_result.add_evidence(item)
        for item in issues:
            scan_result.add_issue(item)

        passed = not any(issue.severity in {"high", "critical"} for issue in issues)
        score_hint = self._compute_score_hint(
            has_tests=has_tests,
            test_file_count=len(test_files),
            framework_count=len(detected_frameworks),
            has_coverage_config=has_coverage_config,
        )

        return ScannerSummary(
            scanner_name=self.scanner_name,
            passed=passed,
            score_hint=score_hint,
            evidence=evidence,
            issues=issues,
            metrics=metrics,
        )

    def _find_test_directories(self, root: Path) -> list[str]:
        found: list[str] = []
        for candidate in self.TEST_DIR_CANDIDATES:
            for path in root.rglob(candidate):
                if path.is_dir():
                    rel = str(path.relative_to(root))
                    if rel not in found:
                        found.append(rel)
        return found

    def _find_test_files(self, root: Path) -> list[str]:
        found: list[str] = []

        patterns = [
            "test_*.py",
            "*_test.py",
            "*.spec.js",
            "*.test.js",
            "*.spec.ts",
            "*.test.ts",
            "*.spec.tsx",
            "*.test.tsx",
        ]

        for pattern in patterns:
            for path in root.rglob(pattern):
                if path.is_file():
                    rel = str(path.relative_to(root))
                    if rel not in found:
                        found.append(rel)

        return sorted(found)

    def _detect_frameworks(self, root: Path) -> list[str]:
        frameworks: list[str] = []

        if self._has_pytest_config(root) or list(root.rglob("test_*.py")) or list(root.rglob("*_test.py")):
            frameworks.append("pytest")

        if self._has_jest_config(root):
            package_json = root / "package.json"
            content = self.safe_read_text(package_json) if package_json.exists() else ""
            if "jest" in content.lower() or "react-scripts test" in content.lower():
                frameworks.append("jest")
            elif (root / "jest.config.js").exists() or (root / "jest.config.ts").exists() or (root / "jest.config.cjs").exists():
                frameworks.append("jest")

        if self._has_vitest_config(root):
            package_json = root / "package.json"
            content = self.safe_read_text(package_json) if package_json.exists() else ""
            if "vitest" in content.lower():
                frameworks.append("vitest")
            elif (root / "vitest.config.ts").exists() or (root / "vitest.config.js").exists():
                frameworks.append("vitest")

        normalized: list[str] = []
        for item in frameworks:
            if item not in normalized:
                normalized.append(item)

        return normalized

    def _has_pytest_config(self, root: Path) -> bool:
        for candidate in self.PYTEST_CONFIG_CANDIDATES:
            path = root / candidate
            if not path.exists():
                continue
            if candidate == "pyproject.toml":
                content = self.safe_read_text(path).lower()
                if "tool.pytest" in content or "pytest.ini_options" in content:
                    return True
            elif candidate == "setup.cfg":
                content = self.safe_read_text(path).lower()
                if "[tool:pytest]" in content:
                    return True
            elif candidate == "tox.ini":
                content = self.safe_read_text(path).lower()
                if "[pytest]" in content:
                    return True
            else:
                return True
        return False

    def _has_jest_config(self, root: Path) -> bool:
        for candidate in self.JEST_CONFIG_CANDIDATES:
            path = root / candidate
            if not path.exists():
                continue
            if candidate == "package.json":
                content = self.safe_read_text(path).lower()
                if '"jest"' in content or "react-scripts test" in content:
                    return True
            else:
                return True
        return False

    def _has_vitest_config(self, root: Path) -> bool:
        for candidate in self.VITEST_CONFIG_CANDIDATES:
            path = root / candidate
            if not path.exists():
                continue
            if candidate == "package.json":
                content = self.safe_read_text(path).lower()
                if '"vitest"' in content:
                    return True
            else:
                return True
        return False

    def _has_coverage_config(self, root: Path) -> bool:
        for candidate in self.COVERAGE_CONFIG_CANDIDATES:
            path = root / candidate
            if not path.exists():
                continue
            if candidate == "pyproject.toml":
                content = self.safe_read_text(path).lower()
                if "tool.coverage" in content or "cov-report" in content or "pytest-cov" in content:
                    return True
            elif candidate == "setup.cfg":
                content = self.safe_read_text(path).lower()
                if "coverage" in content or "pytest-cov" in content:
                    return True
            elif candidate == "tox.ini":
                content = self.safe_read_text(path).lower()
                if "coverage" in content or "pytest-cov" in content:
                    return True
            elif candidate == "package.json":
                content = self.safe_read_text(path).lower()
                if "coverage" in content or "c8" in content or "nyc" in content:
                    return True
            else:
                return True
        return False

    @staticmethod
    def _compute_score_hint(
        *,
        has_tests: bool,
        test_file_count: int,
        framework_count: int,
        has_coverage_config: bool,
    ) -> float:
        if not has_tests:
            return 0.0

        score = 0.35

        if test_file_count >= 10:
            score += 0.35
        elif test_file_count >= 5:
            score += 0.25
        elif test_file_count >= 3:
            score += 0.15
        else:
            score += 0.05

        if framework_count >= 1:
            score += 0.2

        if has_coverage_config:
            score += 0.1

        return min(1.0, round(score, 2))