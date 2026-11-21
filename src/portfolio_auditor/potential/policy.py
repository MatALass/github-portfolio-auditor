"""Load and validate the potential policy and the per-repository overrides."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

_POLICY_DIR = Path(__file__).parent / "policies"


class DomainRule(BaseModel):
    label: str
    role_weight: float = Field(ge=0.0, le=1.0)
    saturation: float = Field(gt=0.0)
    # README keywords alone can reach at most this share of the saturation:
    # a strong domain needs evidence in the code (files, dependencies, paths).
    keyword_cap: float = Field(default=0.5, ge=0.0, le=1.0)
    extensions: dict[str, float] = Field(default_factory=dict)
    dependencies: dict[str, float] = Field(default_factory=dict)
    keywords: dict[str, float] = Field(default_factory=dict)
    paths: dict[str, float] = Field(default_factory=dict)


class RealnessRule(BaseModel):
    saturation: float = Field(gt=0.0)
    keywords: dict[str, float] = Field(default_factory=dict)
    # concrete figures in the README (60,921 rows, 100 000 kills...) are a
    # strong sign the project was run on real data and reports real results
    quantified_weight: float = Field(default=0.4, ge=0.0)
    quantified_cap: float = Field(default=1.6, ge=0.0)


class EffortRule(BaseModel):
    max_effort: float = Field(gt=0.0)
    missing_readme: float = 2
    thin_readme: float = 1
    readme_min_words: int = 300
    missing_tests: float = 2
    missing_ci: float = 1
    missing_visuals: float = 1
    notebook_only: float = 2
    flat_layout: float = 1
    heavy_repo: float = 1
    heavy_repo_kb: int = 50_000
    stale: float = 1
    stale_days: int = 270
    personal_data_tracked: float = 3


class PotentialWeights(BaseModel):
    role_relevance: float = 30
    realness: float = 20
    substance: float = 15
    current_level: float = 15
    feasibility: float = 15
    recency: float = 5

    def normalised(self) -> dict[str, float]:
        raw = self.model_dump()
        total = sum(raw.values())
        if total <= 0:
            raise ValueError("potential weights must sum to a positive value")
        return {k: v / total for k, v in raw.items()}


class SubstanceRule(BaseModel):
    full_credit_code_kb: float = Field(default=150, gt=0)


class RecencyRule(BaseModel):
    full_credit_days: int = 60
    zero_credit_days: int = 540


class PersonalDataRule(BaseModel):
    columns: list[str] = Field(default_factory=list)
    min_hits: int = Field(default=2, ge=1)


class EligibilityRule(BaseModel):
    min_owner_commit_share: float = Field(default=0.3, ge=0.0, le=1.0)
    exclude_name_patterns: list[str] = Field(default_factory=list)


class SelectionRule(BaseModel):
    featured_count: int = Field(default=6, ge=1)
    bench_count: int = Field(default=4, ge=0)
    max_per_theme: int = Field(default=1, ge=1)
    max_per_primary_domain: int = Field(default=2, ge=1)
    domain_similarity_penalty: float = Field(default=0.35, ge=0.0, le=1.0)
    coverage_bonus: float = Field(default=0.15, ge=0.0)
    core_coverage_min_strength: float = Field(default=0.7, ge=0.0, le=1.0)
    core_domains: list[str] = Field(default_factory=list)
    min_role_relevance: float = Field(default=0.35, ge=0.0, le=1.0)
    min_primary_role_weight: float = Field(default=0.5, ge=0.0, le=1.0)


class PotentialPolicy(BaseModel):
    version: str
    target_role: str
    domains: dict[str, DomainRule]
    themes: dict[str, list[str]]
    realness: RealnessRule
    effort: EffortRule
    weights: PotentialWeights
    substance: SubstanceRule = Field(default_factory=SubstanceRule)
    recency: RecencyRule = Field(default_factory=RecencyRule)
    personal_data: PersonalDataRule = Field(default_factory=PersonalDataRule)
    eligibility: EligibilityRule = Field(default_factory=EligibilityRule)
    selection: SelectionRule = Field(default_factory=SelectionRule)

    @field_validator("domains")
    @classmethod
    def _non_empty(cls, value: dict[str, DomainRule]) -> dict[str, DomainRule]:
        if not value:
            raise ValueError("at least one domain is required")
        return value

    def check_core_domains(self) -> None:
        unknown = set(self.selection.core_domains) - set(self.domains)
        if unknown:
            raise ValueError(f"core_domains reference unknown domains: {sorted(unknown)}")


class RepoOverride(BaseModel):
    """Human knowledge the scanners cannot infer.

    ``exclude`` removes the repo from selection (it stays in the table with
    the reason). ``theme`` / ``primary_domain`` correct a wrong detection.
    ``realness_bonus`` (0..1) records a real stakeholder or dataset the README
    does not mention. ``extra_effort`` adds known work the scanners miss
    (label -> effort units). ``note`` is shown in the report.
    """

    exclude: str | None = None
    theme: str | None = None
    primary_domain: str | None = None
    realness_bonus: float = Field(default=0.0, ge=-1.0, le=1.0)
    merge_into: str | None = None
    extra_effort: dict[str, float] = Field(default_factory=dict)
    note: str | None = None


def load_potential_policy(path: Path | None = None, version: str = "v1") -> PotentialPolicy:
    policy_path = path or _POLICY_DIR / f"potential_{version}.yaml"
    data = yaml.safe_load(Path(policy_path).read_text(encoding="utf-8"))
    policy = PotentialPolicy.model_validate(data)
    policy.check_core_domains()
    return policy


def load_overrides(path: Path | None) -> dict[str, RepoOverride]:
    """Overrides YAML: ``{repo_name_or_full_name: {exclude: ..., theme: ...}}``."""
    if path is None:
        return {}
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    repos = data.get("repos", data)
    return {str(k).lower(): RepoOverride.model_validate(v or {}) for k, v in repos.items()}
