from __future__ import annotations

from pathlib import Path

from portfolio_auditor.settings import get_settings


def data_path(*parts: str) -> Path:
    path = get_settings().data_dir.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
