from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from portfolio_auditor.settings import Settings, get_settings
from portfolio_auditor.site.api_schema import SitePayload


class SiteExporter:
    """
    Build and validate the payload consumed by a future site or dashboard layer.
    """

    @staticmethod
    def export_site_payload(output_path: Path, payload: SitePayload) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return output_path

    @staticmethod
    def export_from_processed_owner(
        owner: str,
        *,
        settings: Settings | None = None,
    ) -> Path:
        resolved_settings = settings or get_settings()
        owner_dir = resolved_settings.get_processed_owner_dir(owner)
        ranking_path = owner_dir / "site_payload.json"
        if not ranking_path.exists():
            raise FileNotFoundError(
                f"{ranking_path} not found. Run the full audit pipeline first for owner '{owner}'."
            )

        payload = SitePayload.model_validate(_read_json(ranking_path))
        output_path = owner_dir / "repos_site_data.json"
        return SiteExporter.export_site_payload(output_path, payload)


def export_site_data(owner: str, settings: Settings | None = None) -> Path:
    return SiteExporter.export_from_processed_owner(owner, settings=settings)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))