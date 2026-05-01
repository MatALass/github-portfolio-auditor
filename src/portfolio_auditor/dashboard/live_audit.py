from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from portfolio_auditor.audit_runner import AuditRunner
from portfolio_auditor.dashboard.history import snapshot_current_processed_artifacts
from portfolio_auditor.settings import get_settings, reset_settings_cache


@dataclass(frozen=True)
class AuditRefreshResult:
    owner: str
    analyzed_repo_count: int
    snapshot_dir: Path | None


def ensure_streamlit_secrets_in_env() -> None:
    if not os.getenv("GITHUB_TOKEN"):
        try:
            token = st.secrets.get("GITHUB_TOKEN")  # type: ignore[arg-type]
        except Exception:
            token = None
        if token:
            os.environ["GITHUB_TOKEN"] = str(token)


def run_live_audit(owner: str, *, refresh_clones: bool = True) -> AuditRefreshResult:
    ensure_streamlit_secrets_in_env()
    reset_settings_cache()
    settings = get_settings()
    settings.ensure_directories()

    previous_snapshot = snapshot_current_processed_artifacts(owner, settings)

    runner = AuditRunner(settings)
    try:
        artifacts = runner.run(
            owner=owner,
            refresh_clones=refresh_clones,
            enrich=True,
            export=True,
        )
    finally:
        runner.close()

    return AuditRefreshResult(
        owner=owner,
        analyzed_repo_count=len(artifacts.repos),
        snapshot_dir=previous_snapshot,
    )
