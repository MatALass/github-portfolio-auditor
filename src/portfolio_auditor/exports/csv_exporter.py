from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_review import RepoReview
from portfolio_auditor.models.repo_score import RepoScore


class CsvExporter:
    """
    CSV exporter for ranking tables and flattened audit summaries.
    """

    @staticmethod
    def export_scores_table(
        output_path: Path,
        scores: list[RepoScore],
    ) -> Path:
        rows = [score.to_flat_dict() for score in scores]
        CsvExporter._write_rows(output_path, rows)
        return output_path

    @staticmethod
    def export_reviews_table(
        output_path: Path,
        reviews: list[RepoReview],
    ) -> Path:
        rows = [review.to_flat_dict() for review in reviews]
        CsvExporter._write_rows(output_path, rows)
        return output_path

    @staticmethod
    def export_repo_inventory(
        output_path: Path,
        repos: list[RepoMetadata],
    ) -> Path:
        rows = [repo.to_flat_dict() for repo in repos]
        CsvExporter._write_rows(output_path, rows)
        return output_path

    @staticmethod
    def export_master_table(
        output_path: Path,
        *,
        repos: list[RepoMetadata],
        scores: list[RepoScore],
        reviews: list[RepoReview],
    ) -> Path:
        repo_index = {repo.full_name: repo for repo in repos}
        score_index = {score.repo_full_name: score for score in scores}
        review_index = {review.repo_full_name: review for review in reviews}

        full_names = sorted(
            set(repo_index.keys()) | set(score_index.keys()) | set(review_index.keys())
        )

        rows: list[dict[str, Any]] = []

        for full_name in full_names:
            repo = repo_index.get(full_name)
            score = score_index.get(full_name)
            review = review_index.get(full_name)

            row: dict[str, Any] = {"repo_full_name": full_name}

            if repo is not None:
                row.update(
                    {
                        "repo_name": repo.name,
                        "owner_login": repo.owner.login,
                        "primary_language": repo.language or repo.language_stats.primary_language,
                        "private": repo.flags.private,
                        "archived": repo.flags.archived,
                        "homepage": str(repo.links.homepage) if repo.links.homepage else None,
                        "html_url": str(repo.links.html_url),
                        "topics": ", ".join(repo.topics.items),
                        "description": repo.description,
                    }
                )

            if score is not None:
                row.update(score.to_flat_dict())

            if review is not None:
                row.update(
                    {
                        "portfolio_decision": review.portfolio_decision.value,
                        "executive_summary": review.executive_summary,
                        "portfolio_rationale": review.portfolio_rationale,
                        "recruiter_signal": review.recruiter_signal,
                        "priority_actions": " | ".join(item.text for item in review.priority_actions),
                        "blockers": " | ".join(item.text for item in review.blockers),
                        "quick_wins": " | ".join(item.text for item in review.quick_wins),
                    }
                )

            rows.append(row)

        CsvExporter._write_rows(output_path, rows)
        return output_path

    @staticmethod
    def _write_rows(output_path: Path, rows: list[dict[str, Any]]) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not rows:
            output_path.write_text("", encoding="utf-8")
            return

        fieldnames = CsvExporter._collect_fieldnames(rows)

        with output_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _collect_fieldnames(rows: list[dict[str, Any]]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()

        for row in rows:
            for key in row.keys():
                if key not in seen:
                    ordered.append(key)
                    seen.add(key)

        return ordered