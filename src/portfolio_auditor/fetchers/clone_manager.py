from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.settings import Settings


class CloneError(RuntimeError):
    """
    Raised when a repository cannot be cloned or refreshed.
    """


@dataclass(slots=True)
class CloneResult:
    repo_full_name: str
    local_path: Path
    cloned: bool
    refreshed: bool
    skipped: bool


class CloneManager:
    """
    Handles local repository cloning for deeper file-level analysis.

    Important behavior:
    - public repositories can be cloned anonymously over HTTPS
    - private repositories require an authenticated clone URL
    - SSH remains supported if enabled in settings
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def clone_repo(
        self,
        repo: RepoMetadata,
        *,
        refresh: bool = False,
        shallow: bool = True,
    ) -> CloneResult:
        target_path = self.settings.get_repo_clone_path(repo.full_name)

        if target_path.exists() and not refresh:
            return CloneResult(
                repo_full_name=repo.full_name,
                local_path=target_path,
                cloned=False,
                refreshed=False,
                skipped=True,
            )

        if target_path.exists() and refresh:
            shutil.rmtree(target_path)

        clone_url = self._resolve_clone_url(repo)
        command = ["git", "clone"]

        if shallow:
            command.extend(["--depth", "1"])

        command.extend([clone_url, str(target_path)])

        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise CloneError(
                "Git executable not found. Install Git and ensure it is available in PATH."
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            stdout = (exc.stdout or "").strip()
            details = stderr or stdout or "unknown git clone error"
            raise CloneError(f"Failed to clone {repo.full_name}: {details}") from exc

        return CloneResult(
            repo_full_name=repo.full_name,
            local_path=target_path,
            cloned=True,
            refreshed=refresh,
            skipped=False,
        )

    def clone_many(
        self,
        repos: list[RepoMetadata],
        *,
        refresh: bool = False,
        shallow: bool = True,
    ) -> list[CloneResult]:
        results: list[CloneResult] = []
        for repo in repos:
            result = self.clone_repo(repo, refresh=refresh, shallow=shallow)
            results.append(result)
        return results

    def repo_exists_locally(self, repo_full_name: str) -> bool:
        return self.settings.get_repo_clone_path(repo_full_name).exists()

    def get_local_repo_path(self, repo_full_name: str) -> Path:
        return self.settings.get_repo_clone_path(repo_full_name)

    def _resolve_clone_url(self, repo: RepoMetadata) -> str:
        if self.settings.should_use_ssh_for_clone():
            if not repo.links.ssh_url:
                raise CloneError(
                    f"SSH clone requested but ssh_url is missing for repository {repo.full_name}."
                )
            return repo.links.ssh_url

        if repo.links.clone_url:
            https_clone_url = str(repo.links.clone_url)
            return self._build_authenticated_https_clone_url(https_clone_url)

        raise CloneError(f"HTTPS clone URL is missing for repository {repo.full_name}.")

    def _build_authenticated_https_clone_url(self, clone_url: str) -> str:
        """
        Build an authenticated HTTPS clone URL when a GitHub token is available.

        Example:
            https://github.com/owner/repo.git
        becomes:
            https://x-access-token:<TOKEN>@github.com/owner/repo.git

        Notes:
        - This is only applied to GitHub HTTPS URLs.
        - If no token is available, the original URL is returned unchanged.
        - The authenticated URL must never be logged.
        """
        token = self._resolve_github_token()
        if not token:
            return clone_url

        github_prefix = "https://github.com/"
        if not clone_url.startswith(github_prefix):
            return clone_url

        return clone_url.replace(
            github_prefix,
            f"https://x-access-token:{token}@github.com/",
            1,
        )

    def _resolve_github_token(self) -> str | None:
        """
        Resolve the GitHub token from environment variables.

        This works both:
        - locally when .env is loaded into the environment
        - on Streamlit Community Cloud after secrets are copied into os.environ
        """
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            return None

        token = token.strip()
        return token or None