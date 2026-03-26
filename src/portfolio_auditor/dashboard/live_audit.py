from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from portfolio_auditor.audit_runner import AuditRunner
from portfolio_auditor.collectors.github.client import GitHubApiError, GitHubRateLimitError
from portfolio_auditor.settings import get_settings


ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
PROCESSED_HISTORY_DIR = DATA_DIR / "processed_history"


@dataclass(slots=True)
class AuditRunResult:
    success: bool
    owner: str
    message: str
    output_dir: Path
    history_dir: Path | None = None
    used_token: bool = False
    repo_count: int = 0


def resolve_github_token() -> str | None:
    """
    Resolve the GitHub token from Streamlit secrets first, then environment variables.
    Works both:
    - locally via .env / environment variables
    - on Streamlit Community Cloud via Secrets
    """
    try:
        secret_token = st.secrets.get("GITHUB_TOKEN")
    except Exception:
        secret_token = None

    env_token = os.getenv("GITHUB_TOKEN")

    token = secret_token or env_token
    if not token:
        return None

    token = str(token).strip()
    return token or None


def _timestamp_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _owner_output_dir(owner: str) -> Path:
    return PROCESSED_DIR / owner


def _owner_history_dir(owner: str) -> Path:
    return PROCESSED_HISTORY_DIR / owner


def _snapshot_existing_processed_dir(owner: str) -> Path | None:
    """
    Keep a timestamped backup of the current processed artifacts before refresh.
    """
    current_dir = _owner_output_dir(owner)
    if not current_dir.exists():
        return None

    history_root = _owner_history_dir(owner)
    history_root.mkdir(parents=True, exist_ok=True)

    snapshot_dir = history_root / _timestamp_utc()
    shutil.copytree(current_dir, snapshot_dir)
    return snapshot_dir


def _build_excluded_repo_names(owner: str) -> set[str]:
    """
    Default exclusions:
    - profile README repo: owner/owner
    - this project itself, to avoid self-bias
    Plus optional additions from env or Streamlit secrets.
    """
    excluded = {
        owner.strip().lower(),
        "github-portfolio-auditor",
    }

    try:
        extra = str(st.secrets.get("GITHUB_EXCLUDED_REPO_NAMES", "")).strip()
    except Exception:
        extra = os.getenv("GITHUB_EXCLUDED_REPO_NAMES", "").strip()

    if extra:
        for value in extra.split(","):
            cleaned = value.strip().lower()
            if cleaned:
                excluded.add(cleaned)

    return excluded


def _apply_runtime_github_env(owner: str, token: str | None) -> None:
    """
    Inject runtime environment variables so the existing settings / GitHub client
    can pick them up without changing the whole project architecture.
    """
    if token:
        os.environ["GITHUB_TOKEN"] = token

    excluded_names = ",".join(sorted(_build_excluded_repo_names(owner)))
    os.environ["GITHUB_EXCLUDED_REPO_NAMES"] = excluded_names


def _validate_output(owner: str) -> Path:
    owner_dir = _owner_output_dir(owner)
    required_files = [
        owner_dir / "ranking.json",
        owner_dir / "ranking_summary.json",
        owner_dir / "portfolio_selection.json",
        owner_dir / "redundancy_analysis.json",
    ]

    if not owner_dir.exists():
        raise RuntimeError(
            f"Audit finished without creating the expected owner directory: {owner_dir}"
        )

    missing = [str(path.name) for path in required_files if not path.exists()]
    if missing:
        raise RuntimeError(
            "Audit finished but some required processed artifacts are missing: "
            + ", ".join(missing)
        )

    return owner_dir


def run_fresh_audit(
    owner: str,
    refresh_local_clones: bool = False,
) -> AuditRunResult:
    """
    Launch a fresh GitHub audit directly from Streamlit using the existing Python
    orchestration layer (AuditRunner), not the CLI.

    This is the correct integration point for your project.
    """
    normalized_owner = owner.strip()
    if not normalized_owner:
        raise ValueError("Owner cannot be empty.")

    token = resolve_github_token()
    _apply_runtime_github_env(normalized_owner, token)

    history_dir = _snapshot_existing_processed_dir(normalized_owner)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    settings = get_settings()
    runner = AuditRunner(settings)

    try:
        artifacts = runner.run(
            owner=normalized_owner,
            refresh_clones=refresh_local_clones,
            enrich=True,
            export=True,
        )
    except GitHubRateLimitError as exc:
        raise RuntimeError(
            "GitHub API rate limit exceeded during fresh audit. "
            "Make sure GITHUB_TOKEN is configured correctly."
        ) from exc
    except GitHubApiError as exc:
        raise RuntimeError(f"GitHub collection failed: {exc}") from exc
    finally:
        runner.close()

    output_dir = _validate_output(normalized_owner)

    return AuditRunResult(
        success=True,
        owner=normalized_owner,
        message=f"Fresh audit completed successfully for {normalized_owner}.",
        output_dir=output_dir,
        history_dir=history_dir,
        used_token=bool(token),
        repo_count=len(artifacts.repos),
    )