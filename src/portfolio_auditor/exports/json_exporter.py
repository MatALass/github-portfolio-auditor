from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_review import RepoReview
from portfolio_auditor.models.repo_scan import RepoScanResult
from portfolio_auditor.models.repo_score import RepoScore


class JsonExporter:
    """
    JSON exporter for per-repo and aggregate audit artifacts.
    """

    @staticmethod
    def export_repo_bundle(
        output_path: Path,
        *,
        repo: RepoMetadata,
        scan: RepoScanResult,
        score: RepoScore,
        review: RepoReview,
    ) -> Path:
        payload = {
            "repo": repo.model_dump(mode="json"),
            "scan": scan.model_dump(mode="json"),
            "score": score.model_dump(mode="json"),
            "review": review.model_dump(mode="json"),
        }
        JsonExporter._write_json(output_path, payload)
        return output_path

    @staticmethod
    def export_repo_metadata_list(
        output_path: Path,
        repos: list[RepoMetadata],
    ) -> Path:
        payload = [repo.model_dump(mode="json") for repo in repos]
        JsonExporter._write_json(output_path, payload)
        return output_path

    @staticmethod
    def export_scans(
        output_path: Path,
        scans: list[RepoScanResult],
    ) -> Path:
        payload = [scan.model_dump(mode="json") for scan in scans]
        JsonExporter._write_json(output_path, payload)
        return output_path

    @staticmethod
    def export_scores(
        output_path: Path,
        scores: list[RepoScore],
    ) -> Path:
        payload = [score.model_dump(mode="json") for score in scores]
        JsonExporter._write_json(output_path, payload)
        return output_path

    @staticmethod
    def export_reviews(
        output_path: Path,
        reviews: list[RepoReview],
    ) -> Path:
        payload = [review.model_dump(mode="json") for review in reviews]
        JsonExporter._write_json(output_path, payload)
        return output_path

    @staticmethod
    def export_site_payload(
        output_path: Path,
        rows: list[dict[str, Any]],
    ) -> Path:
        JsonExporter._write_json(output_path, rows)
        return output_path

    @staticmethod
    def _write_json(output_path: Path, payload: Any) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )