from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from portfolio_auditor.settings import Settings

SNAPSHOT_FILES = [
    "ranking.json",
    "ranking_summary.json",
    "portfolio_selection.json",
    "redundancy_analysis.json",
    "site_payload.json",
    "repos_site_data.json",
    "repo_reviews.json",
    "repo_scores.json",
    "repo_scans.json",
    "repos_metadata.json",
]


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def list_snapshots(owner: str, settings: Settings) -> list[Path]:
    history_dir = settings.get_processed_history_owner_dir(owner)
    if not history_dir.exists():
        return []
    return sorted((path for path in history_dir.iterdir() if path.is_dir()), key=lambda item: item.name)


def latest_snapshot_dir(owner: str, settings: Settings) -> Path | None:
    snapshots = list_snapshots(owner, settings)
    return snapshots[-1] if snapshots else None


def snapshot_current_processed_artifacts(owner: str, settings: Settings) -> Path | None:
    source_dir = settings.get_processed_owner_dir(owner)
    if not source_dir.exists():
        return None

    if not any((source_dir / file_name).exists() for file_name in SNAPSHOT_FILES):
        return None

    snapshot_dir = settings.get_processed_history_owner_dir(owner) / _utc_timestamp()
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    copied_files: list[str] = []
    for file_name in SNAPSHOT_FILES:
        source_path = source_dir / file_name
        if not source_path.exists():
            continue
        shutil.copy2(source_path, snapshot_dir / file_name)
        copied_files.append(file_name)

    metadata = {
        "owner": owner,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "copied_files": copied_files,
        "source_dir": str(source_dir),
    }
    (snapshot_dir / "snapshot_meta.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return snapshot_dir


def load_snapshot_meta(snapshot_dir: Path) -> dict[str, Any]:
    path = snapshot_dir / "snapshot_meta.json"
    if not path.exists():
        return {"snapshot_label": snapshot_dir.name}
    return json.loads(path.read_text(encoding="utf-8"))
