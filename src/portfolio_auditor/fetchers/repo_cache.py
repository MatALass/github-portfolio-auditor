from __future__ import annotations

from pathlib import Path

from portfolio_auditor.settings import get_settings


def clones_root() -> Path:
    root = get_settings().data_dir / "raw" / "clones"
    root.mkdir(parents=True, exist_ok=True)
    return root
