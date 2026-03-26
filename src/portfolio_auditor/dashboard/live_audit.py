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
SRC_DIR = ROOT_DIR / "src"
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
    current_dir = _owner_output_dir(owner)
    if not current_dir.exists():
        return None

    history_root = _owner_history_dir(owner)
    history_root.mkdir(parents=True, exist_ok=True)

    snapshot_dir = history_root / _timestamp_utc()
    shutil.copytree(current_dir, snapshot_dir)
    return snapshot_dir


def _build_excluded_repo_names(owner: str) -> str:
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
    candidates: list[tuple[str, str]] = [
        ("portfolio_auditor.audit_runner", "run_full_audit"),
        ("portfolio_auditor.cli", "run_full_audit"),
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
            continue

    return False


def _call_runner_function(
    fn: Callable[..., Any],
    owner: str,
    token: str | None,
    refresh_local_clones: bool,
) -> Any:
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


def _build_subprocess_env(token: str | None, owner: str) -> dict[str, str]:
    env = os.environ.copy()

    if token:
        env["GITHUB_TOKEN"] = token

    env["GITHUB_EXCLUDED_REPO_NAMES"] = _build_excluded_repo_names(owner)

    existing_pythonpath = env.get("PYTHONPATH", "").strip()
    src_path = str(SRC_DIR)

    if existing_pythonpath:
        env["PYTHONPATH"] = f"{src_path}{os.pathsep}{existing_pythonpath}"
    else:
        env["PYTHONPATH"] = src_path

    return env


def _run_cli_subprocess(
    owner: str,
    token: str | None,
    refresh_local_clones: bool,
) -> None:
    env = _build_subprocess_env(token=token, owner=owner)

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
            f"Details: {message}"
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