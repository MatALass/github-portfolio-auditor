from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

SeverityLevel = Literal["info", "low", "medium", "high", "critical"]


class EvidenceItem(BaseModel):
    """
    Concrete proof collected during scanning.
    """

    source: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    path: str | None = None
    value: str | int | float | bool | None = None

    @field_validator("source", "message", mode="before")
    @classmethod
    def strip_required_strings(cls, value: Any) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("field cannot be empty")
        return text

    @field_validator("path", mode="before")
    @classmethod
    def normalize_optional_path(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class IssueItem(BaseModel):
    """
    Structured issue detected by a scanner.
    """

    code: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    severity: SeverityLevel = "medium"
    scanner: str = Field(..., min_length=1)
    path: str | None = None
    recommendation: str | None = None

    @field_validator("code", "title", "description", "scanner", mode="before")
    @classmethod
    def strip_required_strings(cls, value: Any) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("field cannot be empty")
        return text

    @field_validator("path", "recommendation", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class ScannerSummary(BaseModel):
    """
    Summary output for a single scanner.
    """

    scanner_name: str = Field(..., min_length=1)
    passed: bool = True
    score_hint: float | None = Field(default=None, ge=0.0, le=1.0)
    findings_count: int = Field(default=0, ge=0)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    issues: list[IssueItem] = Field(default_factory=list)
    metrics: dict[str, int | float | str | bool | None] = Field(default_factory=dict)

    @field_validator("scanner_name", mode="before")
    @classmethod
    def strip_scanner_name(cls, value: Any) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("scanner_name cannot be empty")
        return text

    @field_validator("findings_count", mode="before")
    @classmethod
    def coerce_findings_count(cls, value: Any) -> int:
        if value is None:
            return 0
        return int(value)

    def recompute_findings_count(self) -> None:
        self.findings_count = len(self.issues)


class StructureScan(BaseModel):
    has_src_dir: bool = False
    has_app_dir: bool = False
    has_tests_dir: bool = False
    has_docs_dir: bool = False
    has_data_dir: bool = False
    has_scripts_dir: bool = False
    root_file_count: int = Field(default=0, ge=0)
    large_root_files: list[str] = Field(default_factory=list)
    layout_type: str | None = None
    notes: list[str] = Field(default_factory=list)


class DocumentationScan(BaseModel):
    has_readme: bool = False
    readme_path: str | None = None
    readme_word_count: int = Field(default=0, ge=0)
    has_installation_section: bool = False
    has_usage_section: bool = False
    has_architecture_section: bool = False
    has_results_section: bool = False
    has_roadmap_section: bool = False
    has_license_file: bool = False
    has_env_example: bool = False
    has_screenshots_or_assets: bool = False
    notes: list[str] = Field(default_factory=list)


class TestingScan(BaseModel):
    has_tests: bool = False
    test_file_count: int = Field(default=0, ge=0)
    test_directories: list[str] = Field(default_factory=list)
    detected_frameworks: list[str] = Field(default_factory=list)
    has_pytest_config: bool = False
    has_jest_config: bool = False
    has_vitest_config: bool = False
    has_coverage_config: bool = False
    notes: list[str] = Field(default_factory=list)


class CiScan(BaseModel):
    has_github_actions: bool = False
    workflow_count: int = Field(default=0, ge=0)
    workflow_files: list[str] = Field(default_factory=list)
    has_test_workflow: bool = False
    has_lint_workflow: bool = False
    has_build_workflow: bool = False
    notes: list[str] = Field(default_factory=list)


class DeliveryCleanlinessScan(BaseModel):
    has_gitignore: bool = False
    committed_virtualenv: bool = False
    committed_pycache: bool = False
    committed_pytest_cache: bool = False
    committed_build_artifacts: bool = False
    committed_egg_info: bool = False
    oversized_files: list[str] = Field(default_factory=list)
    suspicious_generated_files: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RepoScanResult(BaseModel):
    """
    Canonical result of repo scanning before scoring.
    """

    repo_name: str = Field(..., min_length=1)
    repo_full_name: str = Field(..., min_length=1)
    local_path: str | None = None

    structure: StructureScan = Field(default_factory=StructureScan)
    documentation: DocumentationScan = Field(default_factory=DocumentationScan)
    testing: TestingScan = Field(default_factory=TestingScan)
    ci: CiScan = Field(default_factory=CiScan)
    cleanliness: DeliveryCleanlinessScan = Field(default_factory=DeliveryCleanlinessScan)

    scanner_summaries: list[ScannerSummary] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    issues: list[IssueItem] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("repo_name", "repo_full_name", mode="before")
    @classmethod
    def strip_required_strings(cls, value: Any) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("field cannot be empty")
        return text

    @field_validator("local_path", mode="before")
    @classmethod
    def normalize_local_path(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("tags must be a list")
        normalized: list[str] = []
        for item in value:
            tag = str(item).strip().lower()
            if tag and tag not in normalized:
                normalized.append(tag)
        return normalized

    def add_issue(self, issue: IssueItem) -> None:
        self.issues.append(issue)

    def add_evidence(self, evidence: EvidenceItem) -> None:
        self.evidence.append(evidence)

    def add_scanner_summary(self, summary: ScannerSummary) -> None:
        summary.recompute_findings_count()
        self.scanner_summaries.append(summary)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def critical_issue_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "critical")

    @property
    def high_issue_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "high")

    def issues_by_severity(self) -> dict[str, int]:
        levels = ["info", "low", "medium", "high", "critical"]
        return {level: sum(1 for issue in self.issues if issue.severity == level) for level in levels}