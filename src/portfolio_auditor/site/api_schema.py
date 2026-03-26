from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class SiteRepositoryCard(BaseModel):
    rank: int = Field(..., ge=1)
    repo_name: str
    repo_full_name: str
    global_score: float = Field(..., ge=0.0, le=100.0)
    score_label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    portfolio_decision: str
    primary_language: str | None = None
    description: str | None = None
    owner_login: str
    html_url: HttpUrl
    homepage: HttpUrl | None = None
    strengths_count: int = Field(default=0, ge=0)
    weaknesses_count: int = Field(default=0, ge=0)
    blockers_count: int = Field(default=0, ge=0)
    priority_actions_count: int = Field(default=0, ge=0)
    stars: int = Field(default=0, ge=0)
    forks: int = Field(default=0, ge=0)
    overlap_cluster_id: str | None = None
    overlap_candidate_count: int = Field(default=0, ge=0)
    strongest_overlap_score: float = Field(default=0.0, ge=0.0, le=1.0)
    redundancy_status: str
    redundancy_reason: str | None = None
    representative_repo_full_name: str | None = None


class SitePortfolioBucket(BaseModel):
    label: str
    count: int = Field(..., ge=0)
    repos: list[str] = Field(default_factory=list)


class SitePortfolioOverview(BaseModel):
    total_repositories: int = Field(..., ge=0)
    featured_count: int = Field(..., ge=0)
    keep_visible_but_improve_count: int = Field(..., ge=0)
    improvement_backlog_count: int = Field(..., ge=0)
    archive_candidates_count: int = Field(..., ge=0)
    private_candidates_count: int = Field(..., ge=0)
    redundancy_candidates_count: int = Field(..., ge=0)
    overlap_clusters_count: int = Field(..., ge=0)
    manager_summary: str
    decision_buckets: list[SitePortfolioBucket] = Field(default_factory=list)


class SitePayload(BaseModel):
    generated_for_owner: str
    overview: SitePortfolioOverview
    repositories: list[SiteRepositoryCard] = Field(default_factory=list)