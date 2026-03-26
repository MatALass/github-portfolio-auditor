from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RepoOwner(BaseModel):
    """
    Basic GitHub owner information.

    Internal domain model:
    URLs are kept as plain strings to avoid over-constraining the collection layer.
    Strict URL validation should happen only at external contract boundaries
    (for example site/API payloads).
    """

    login: str = Field(..., min_length=1)
    owner_type: str = Field(..., alias="type", min_length=1)
    html_url: str | None = None

    model_config = {"populate_by_name": True}

    @field_validator("login", "owner_type", mode="before")
    @classmethod
    def strip_required_strings(cls, value: Any) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("field cannot be empty")
        return text

    @field_validator("html_url", mode="before")
    @classmethod
    def normalize_optional_url(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class RepoLicense(BaseModel):
    """
    Repository license metadata.
    """

    key: str | None = None
    name: str | None = None
    spdx_id: str | None = None
    url: str | None = None

    @field_validator("key", "name", "spdx_id", "url", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class RepoLanguageStats(BaseModel):
    """
    Language usage statistics for a repository.
    Values typically come from GitHub language byte counts.
    """

    languages: dict[str, int] = Field(default_factory=dict)

    @property
    def total_bytes(self) -> int:
        return sum(self.languages.values())

    @property
    def primary_language(self) -> str | None:
        if not self.languages:
            return None
        return max(self.languages.items(), key=lambda item: item[1])[0]

    def language_share(self, language: str) -> float:
        total = self.total_bytes
        if total <= 0:
            return 0.0
        return self.languages.get(language, 0) / total


class RepoTopics(BaseModel):
    """
    Normalized repository topics.
    """

    items: list[str] = Field(default_factory=list)

    @field_validator("items", mode="before")
    @classmethod
    def normalize_topics(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("topics must be provided as a list")
        normalized: list[str] = []
        for item in value:
            if item is None:
                continue
            topic = str(item).strip().lower()
            if topic and topic not in normalized:
                normalized.append(topic)
        return normalized


class RepoFlags(BaseModel):
    """
    Repository state flags.
    """

    private: bool = False
    fork: bool = False
    archived: bool = False
    disabled: bool = False
    is_template: bool = False
    has_issues: bool = True
    has_projects: bool = False
    has_wiki: bool = False
    has_pages: bool = False
    has_discussions: bool = False


class RepoEngagement(BaseModel):
    """
    Repository engagement metrics from GitHub metadata.
    """

    stargazers_count: int = Field(default=0, ge=0)
    watchers_count: int = Field(default=0, ge=0)
    forks_count: int = Field(default=0, ge=0)
    open_issues_count: int = Field(default=0, ge=0)
    subscribers_count: int | None = Field(default=None, ge=0)
    network_count: int | None = Field(default=None, ge=0)

    @field_validator(
        "stargazers_count",
        "watchers_count",
        "forks_count",
        "open_issues_count",
        "subscribers_count",
        "network_count",
        mode="before",
    )
    @classmethod
    def coerce_ints(cls, value: Any) -> int | None:
        if value is None:
            return None
        return int(value)


class RepoTimestamps(BaseModel):
    """
    Repository timeline metadata.
    """

    created_at: datetime
    updated_at: datetime
    pushed_at: datetime | None = None

    @field_validator("created_at", "updated_at", "pushed_at", mode="before")
    @classmethod
    def parse_datetime(cls, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


class RepoLinks(BaseModel):
    """
    Relevant repository URLs.

    Internal domain model uses strings rather than HttpUrl to keep GitHub ingestion
    resilient and serialization-warning-free.
    """

    html_url: str
    clone_url: str | None = None
    ssh_url: str | None = None
    homepage: str | None = None

    @field_validator("html_url", mode="before")
    @classmethod
    def normalize_required_url(cls, value: Any) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("html_url cannot be empty")
        return text

    @field_validator("clone_url", "ssh_url", "homepage", mode="before")
    @classmethod
    def normalize_optional_url(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class RepoMetadata(BaseModel):
    """
    Canonical normalized repository metadata used across the audit pipeline.

    This is an internal domain model. It should remain stable and serialization-safe.
    Strict URL validation belongs to explicit external schemas, not to raw collection.
    """

    id: int = Field(..., ge=1)
    name: str = Field(..., min_length=1)
    full_name: str = Field(..., min_length=1)
    description: str | None = None
    default_branch: str = Field(default="main", min_length=1)
    size_kb: int = Field(default=0, ge=0)

    owner: RepoOwner
    flags: RepoFlags = Field(default_factory=RepoFlags)
    engagement: RepoEngagement = Field(default_factory=RepoEngagement)
    timestamps: RepoTimestamps
    links: RepoLinks

    language: str | None = None
    language_stats: RepoLanguageStats = Field(default_factory=RepoLanguageStats)
    topics: RepoTopics = Field(default_factory=RepoTopics)
    license: RepoLicense | None = None

    readme_download_url: str | None = None

    @field_validator("name", "full_name", "default_branch", mode="before")
    @classmethod
    def strip_required_strings(cls, value: Any) -> str:
        if value is None:
            raise ValueError("required string field cannot be null")
        text = str(value).strip()
        if not text:
            raise ValueError("required string field cannot be empty")
        return text

    @field_validator("description", "language", "readme_download_url", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("size_kb", mode="before")
    @classmethod
    def coerce_size(cls, value: Any) -> int:
        if value is None:
            return 0
        return int(value)

    @property
    def owner_login(self) -> str:
        return self.owner.login

    @property
    def is_public(self) -> bool:
        return not self.flags.private

    @property
    def repo_slug(self) -> str:
        return self.full_name.lower()

    def to_flat_dict(self) -> dict[str, Any]:
        """
        Flatten the most useful metadata for CSV exports or quick tabular analysis.
        """
        return {
            "id": self.id,
            "name": self.name,
            "full_name": self.full_name,
            "owner_login": self.owner.login,
            "owner_type": self.owner.owner_type,
            "description": self.description,
            "default_branch": self.default_branch,
            "private": self.flags.private,
            "fork": self.flags.fork,
            "archived": self.flags.archived,
            "disabled": self.flags.disabled,
            "is_template": self.flags.is_template,
            "has_issues": self.flags.has_issues,
            "has_projects": self.flags.has_projects,
            "has_wiki": self.flags.has_wiki,
            "has_pages": self.flags.has_pages,
            "has_discussions": self.flags.has_discussions,
            "primary_language": self.language,
            "detected_primary_language": self.language_stats.primary_language,
            "topics": ", ".join(self.topics.items),
            "license_name": self.license.name if self.license else None,
            "stargazers_count": self.engagement.stargazers_count,
            "watchers_count": self.engagement.watchers_count,
            "forks_count": self.engagement.forks_count,
            "open_issues_count": self.engagement.open_issues_count,
            "size_kb": self.size_kb,
            "html_url": self.links.html_url,
            "homepage": self.links.homepage,
            "clone_url": self.links.clone_url,
            "readme_download_url": self.readme_download_url,
            "created_at": self.timestamps.created_at.isoformat(),
            "updated_at": self.timestamps.updated_at.isoformat(),
            "pushed_at": self.timestamps.pushed_at.isoformat()
            if self.timestamps.pushed_at
            else None,
        }