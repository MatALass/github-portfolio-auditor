from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from portfolio_auditor.settings import Settings


class GitHubApiError(RuntimeError):
    """
    Base GitHub API error.
    """


class GitHubRateLimitError(GitHubApiError):
    """
    Raised when the GitHub API rate limit has been exceeded.
    """

    def __init__(
        self,
        message: str,
        *,
        reset_at: datetime | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.reset_at = reset_at
        self.retry_after_seconds = retry_after_seconds


class GitHubNotFoundError(GitHubApiError):
    """
    Raised when a requested GitHub resource does not exist.
    """


class GitHubClient:
    """
    Thin GitHub REST API client for repository metadata collection.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.github_api_base_url.rstrip("/")
        self.timeout = settings.github_request_timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(settings.github_headers)
        self._authenticated_user_cache: dict[str, Any] | None = None
        self._authenticated_user_loaded = False

    def close(self) -> None:
        self.session.close()

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = self._build_url(path)
        response = self.session.request(
            method=method,
            url=url,
            params=params,
            timeout=self.timeout,
        )

        if response.status_code >= 400:
            self._raise_for_error(response)

        if response.status_code == 204 or not response.text.strip():
            return None

        return response.json()

    def _raise_for_error(self, response: requests.Response) -> None:
        message = self._extract_error_message(response)
        status_code = response.status_code

        if status_code == 404:
            raise GitHubNotFoundError(
                f"GitHub resource not found: {response.request.method} {response.url}. {message}"
            )

        if status_code == 403 and self._looks_like_rate_limit(response, message):
            reset_at = self._extract_rate_limit_reset(response)
            retry_after_seconds = self._extract_retry_after_seconds(response)
            suffix = ""
            if reset_at is not None:
                suffix = f" Rate limit resets at {reset_at.isoformat()}."
            raise GitHubRateLimitError(
                f"GitHub API rate limit exceeded.{suffix} {message}".strip(),
                reset_at=reset_at,
                retry_after_seconds=retry_after_seconds,
            )

        raise GitHubApiError(
            f"GitHub API request failed: {status_code} {response.reason}. {message}"
        )

    @staticmethod
    def _extract_error_message(response: requests.Response) -> str:
        try:
            payload = response.json()
        except Exception:
            return response.text.strip()

        if isinstance(payload, dict):
            message = payload.get("message")
            documentation_url = payload.get("documentation_url")
            parts = []
            if message:
                parts.append(str(message))
            if documentation_url:
                parts.append(f"See: {documentation_url}")
            return " ".join(parts).strip()

        return str(payload)

    @staticmethod
    def _looks_like_rate_limit(response: requests.Response, message: str) -> bool:
        lowered = message.lower()
        remaining = response.headers.get("X-RateLimit-Remaining")
        return (
            "rate limit exceeded" in lowered
            or "api rate limit exceeded" in lowered
            or remaining == "0"
        )

    @staticmethod
    def _extract_rate_limit_reset(response: requests.Response) -> datetime | None:
        raw = response.headers.get("X-RateLimit-Reset")
        if not raw:
            return None
        try:
            timestamp = int(raw)
        except ValueError:
            return None
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    @staticmethod
    def _extract_retry_after_seconds(response: requests.Response) -> int | None:
        raw = response.headers.get("Retry-After")
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    def get_user(self, username: str) -> dict[str, Any]:
        return self._request("GET", f"/users/{username}")

    def get_org(self, org_name: str) -> dict[str, Any]:
        return self._request("GET", f"/orgs/{org_name}")

    def get_authenticated_user(self) -> dict[str, Any] | None:
        if self._authenticated_user_loaded:
            return self._authenticated_user_cache

        if not self.settings.github_token:
            self._authenticated_user_cache = None
            self._authenticated_user_loaded = True
            return None

        payload = self._request("GET", "/user")
        if not isinstance(payload, dict):
            self._authenticated_user_cache = None
            self._authenticated_user_loaded = True
            return None

        self._authenticated_user_cache = payload
        self._authenticated_user_loaded = True
        return payload

    def get_authenticated_login(self) -> str | None:
        payload = self.get_authenticated_user()
        if not payload:
            return None
        login = payload.get("login")
        if not isinstance(login, str) or not login.strip():
            return None
        return login.strip()

    def list_user_repos(
        self,
        username: str,
        *,
        sort: str = "updated",
        direction: str = "desc",
    ) -> list[dict[str, Any]]:
        repos: list[dict[str, Any]] = []
        page = 1

        while True:
            batch = self._request(
                "GET",
                f"/users/{username}/repos",
                params={
                    "per_page": self.settings.github_max_repos_per_page,
                    "page": page,
                    "sort": sort,
                    "direction": direction,
                },
            )
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < self.settings.github_max_repos_per_page:
                break
            page += 1

        return repos

    def list_authenticated_user_repos(
        self,
        *,
        sort: str = "updated",
        direction: str = "desc",
    ) -> list[dict[str, Any]]:
        repos: list[dict[str, Any]] = []
        page = 1

        while True:
            batch = self._request(
                "GET",
                "/user/repos",
                params={
                    "visibility": "all",
                    "affiliation": "owner",
                    "per_page": self.settings.github_max_repos_per_page,
                    "page": page,
                    "sort": sort,
                    "direction": direction,
                },
            )
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < self.settings.github_max_repos_per_page:
                break
            page += 1

        return repos

    def list_org_repos(
        self,
        org_name: str,
        *,
        sort: str = "updated",
        direction: str = "desc",
    ) -> list[dict[str, Any]]:
        repos: list[dict[str, Any]] = []
        page = 1

        while True:
            batch = self._request(
                "GET",
                f"/orgs/{org_name}/repos",
                params={
                    "per_page": self.settings.github_max_repos_per_page,
                    "page": page,
                    "sort": sort,
                    "direction": direction,
                },
            )
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < self.settings.github_max_repos_per_page:
                break
            page += 1

        return repos

    def get_repo(self, full_name: str) -> dict[str, Any]:
        return self._request("GET", f"/repos/{full_name}")

    def get_repo_languages(self, full_name: str) -> dict[str, int]:
        payload = self._request("GET", f"/repos/{full_name}/languages")
        if not isinstance(payload, dict):
            return {}
        return {str(key): int(value) for key, value in payload.items()}

    def get_repo_readme(self, full_name: str) -> dict[str, Any] | None:
        try:
            payload = self._request("GET", f"/repos/{full_name}/readme")
        except GitHubNotFoundError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def get_repo_tree(self, full_name: str, branch: str) -> dict[str, Any]:
        ref = self._request("GET", f"/repos/{full_name}/git/ref/heads/{branch}")
        sha = ref["object"]["sha"]
        payload = self._request(
            "GET",
            f"/repos/{full_name}/git/trees/{sha}",
            params={"recursive": 1},
        )
        if not isinstance(payload, dict):
            return {}
        return payload

    def get_rate_limit(self) -> dict[str, Any]:
        return self._request("GET", "/rate_limit")