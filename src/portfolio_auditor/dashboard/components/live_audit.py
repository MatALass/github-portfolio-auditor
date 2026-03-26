from __future__ import annotations

import inspect
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Callable

import streamlit as st


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


def resolve_github_token() -> str | None:
    """
    Resolve the GitHub token from Streamlit secrets first, then environment variables.
    This makes the same code work:
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
    If current processed artifacts exist, keep a timestamped backup before refresh.
    This does not affect the current dashboard behavior, but it gives you a clean
    history trail for future comparisons.
    """
    current_dir = _owner_output_dir(owner)
    if not current_dir.exists():
        return None

    history_root = _owner_history_dir(owner)
    history_root.mkdir(parents=True, exist_ok=True)

    snapshot_dir = history_root / _timestamp_utc()
    shutil.copytree(current_dir, snapshot_dir)
    return snapshot_dir


def _build_excluded_repo_names(owner: str) -> str:
    """
    Default exclusions:
    - profile README repo: owner/owner
    - this project itself, to avoid self-bias
    Plus optional additions from env or Streamlit secrets.
    """
    default_names = {
        owner.lower(),
        "github-portfolio-auditor",
    }

    extra = ""
    try:
        extra = str(st.secrets.get("GITHUB_EXCLUDED_REPO_NAMES", "")).strip()
    except Exception:
        extra = os.getenv("GITHUB_EXCLUDED_REPO_NAMES", "").strip()

    if extra:
        for value in extra.split(","):
            cleaned = value.strip().lower()
            if cleaned:
                default_names.add(cleaned)

    return ",".join(sorted(default_names))


def _try_call_python_runner(
    owner: str,
    token: str | None,
    refresh_local_clones: bool,
) -> bool:
    """
    Prefer reusing an internal Python orchestrator if the project exposes one.

    We try a few common module/function locations. The call is made dynamically
    so this file stays compatible even if your current project structure evolves.
    """
    candidates: list[tuple[str, str]] = [
        ("portfolio_auditor.cli", "run_full_audit"),
        ("portfolio_auditor.audit_runner", "run_full_audit"),
        ("portfolio_auditor.runner", "run_full_audit"),
        ("portfolio_auditor.main", "run_full_audit"),
    ]

    for module_name, function_name in candidates:
        try:
            module = import_module(module_name)
            fn = getattr(module, function_name, None)
            if fn is None or not callable(fn):
                continue

            _call_runner_function(
                fn=fn,
                owner=owner,
                token=token,
                refresh_local_clones=refresh_local_clones,
            )
            return True
        except Exception:
            # We intentionally swallow and continue to the next candidate.
            # The subprocess fallback below will still give you a useful path.
            continue

    return False


def _call_runner_function(
    fn: Callable[..., Any],
    owner: str,
    token: str | None,
    refresh_local_clones: bool,
) -> Any:
    """
    Call the internal runner with best-effort signature adaptation.
    This avoids hard-coding one exact function signature.
    """
    signature = inspect.signature(fn)
    kwargs: dict[str, Any] = {}

    for param_name in signature.parameters:
        lowered = param_name.lower()

        if lowered in {"owner", "github_owner", "username", "account"}:
            kwargs[param_name] = owner
        elif lowered in {"output_dir", "output_path", "output_root"}:
            kwargs[param_name] = str(PROCESSED_DIR)
        elif lowered in {"github_token", "token", "access_token"} and token:
            kwargs[param_name] = token
        elif lowered in {"refresh_local_clones", "refresh_clones", "refresh_clone"}:
            kwargs[param_name] = refresh_local_clones
        elif lowered in {"excluded_repo_names", "excluded_names"}:
            kwargs[param_name] = _build_excluded_repo_names(owner)

    return fn(**kwargs)


def _run_cli_subprocess(
    owner: str,
    token: str | None,
    refresh_local_clones: bool,
) -> None:
    """
    Fallback path when there is no importable Python runner exposed cleanly.

    This assumes your CLI module supports:
      python -m portfolio_auditor.cli --github-owner <owner> --output <dir>

    If your actual CLI arguments differ, adapt only this command block.
    """
    env = os.environ.copy()

    if token:
        env["GITHUB_TOKEN"] = token

    env["GITHUB_EXCLUDED_REPO_NAMES"] = _build_excluded_repo_names(owner)

    cmd = [
        sys.executable,
        "-m",
        "portfolio_auditor.cli",
        "--github-owner",
        owner,
        "--output",
        str(PROCESSED_DIR),
    ]

    if refresh_local_clones:
        cmd.append("--refresh-local-clones")

    completed = subprocess.run(
        cmd,
        cwd=str(ROOT_DIR),
        env=env,
        text=True,
        capture_output=True,
    )

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        message = stderr or stdout or "Unknown CLI execution failure."
        raise RuntimeError(
            "Fresh audit failed via CLI fallback.\n\n"
            f"Command: {' '.join(cmd)}\n\n"
            f"Details:\n{message}"
        )


def _validate_output(owner: str) -> Path:
    owner_dir = _owner_output_dir(owner)
    ranking_path = owner_dir / "ranking.json"

    if not owner_dir.exists():
        raise RuntimeError(
            f"Audit finished without creating the expected owner directory: {owner_dir}"
        )

    if not ranking_path.exists():
        raise RuntimeError(
            f"Audit finished but ranking.json was not found at: {ranking_path}"
        )

    return owner_dir


def run_fresh_audit(
    owner: str,
    refresh_local_clones: bool = False,
) -> AuditRunResult:
    """
    Launch a fresh GitHub audit from the Streamlit app.

    Behavior:
    - resolves the GitHub token from Streamlit secrets or environment
    - snapshots the previous processed owner directory if present
    - reuses an internal Python runner if available
    - otherwise falls back to the CLI module
    """
    normalized_owner = owner.strip()
    if not normalized_owner:
        raise ValueError("Owner cannot be empty.")

    token = resolve_github_token()
    history_dir = _snapshot_existing_processed_dir(normalized_owner)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    python_runner_worked = _try_call_python_runner(
        owner=normalized_owner,
        token=token,
        refresh_local_clones=refresh_local_clones,
    )

    if not python_runner_worked:
        _run_cli_subprocess(
            owner=normalized_owner,
            token=token,
            refresh_local_clones=refresh_local_clones,
        )

    output_dir = _validate_output(normalized_owner)

    return AuditRunResult(
        success=True,
        owner=normalized_owner,
        message=f"Fresh audit completed successfully for {normalized_owner}.",
        output_dir=output_dir,
        history_dir=history_dir,
        used_token=bool(token),
    )