from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from portfolio_auditor.collectors.github.client import GitHubClient
from portfolio_auditor.collectors.github.collector import GitHubCollector
from portfolio_auditor.exports.csv_exporter import CsvExporter
from portfolio_auditor.exports.json_exporter import JsonExporter
from portfolio_auditor.fetchers.clone_manager import CloneManager, CloneResult
from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_review import RepoReview
from portfolio_auditor.models.repo_scan import RepoScanResult
from portfolio_auditor.models.repo_score import RepoScore
from portfolio_auditor.ranking.portfolio_selection import PortfolioSelection, PortfolioSelector
from portfolio_auditor.ranking.ranker import Ranker, RankingSummary
from portfolio_auditor.reviewing.deterministic_review import DeterministicReviewer
from portfolio_auditor.scanners import (
    CiScanner,
    DeliveryCleanlinessScanner,
    DocumentationScanner,
    StructureScanner,
    TestingScanner,
)
from portfolio_auditor.scoring.engine import ScoringEngine
from portfolio_auditor.settings import Settings
from portfolio_auditor.site.transformers import build_site_payload


@dataclass(slots=True)
class AuditArtifacts:
    repos: list[RepoMetadata]
    clone_results: list[CloneResult]
    scans: list[RepoScanResult]
    scores: list[RepoScore]
    reviews: list[RepoReview]
    ranking: RankingSummary | None = None
    selection: PortfolioSelection | None = None


class AuditRunner:
    """
    Main orchestration layer for the deterministic audit pipeline.

    Responsibilities:
    - collect GitHub metadata
    - enrich metadata
    - clone repositories locally
    - run scanners
    - compute scores
    - generate reviews
    - rank repositories for portfolio decisions
    - export JSON/CSV/site artifacts
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = GitHubClient(settings)
        self.collector = GitHubCollector(self.client, settings)
        self.clone_manager = CloneManager(settings)
        self.scoring_engine = ScoringEngine()
        self.reviewer = DeterministicReviewer()
        self.ranker = Ranker()
        self.selector = PortfolioSelector()
        self.scanners = [
            StructureScanner(),
            DocumentationScanner(),
            TestingScanner(),
            CiScanner(),
            DeliveryCleanlinessScanner(),
        ]

    def close(self) -> None:
        self.client.close()

    def run(
        self,
        *,
        owner: str,
        refresh_clones: bool = False,
        enrich: bool = True,
        export: bool = True,
    ) -> AuditArtifacts:
        repos = self.collector.collect_owner_repos(owner)
        if enrich:
            repos = self.collector.enrich_repos(repos)
        self.collector.persist_raw_owner_snapshot(owner, repos)

        clone_results = self.clone_manager.clone_many(
            repos,
            refresh=refresh_clones,
            shallow=True,
        )

        scans: list[RepoScanResult] = []
        scores: list[RepoScore] = []
        reviews: list[RepoReview] = []

        for repo in repos:
            local_path = self.settings.get_repo_clone_path(repo.full_name)
            scan = self.scan_repo(repo, local_path)
            score = self.scoring_engine.score(repo, scan)
            review = self.reviewer.review(repo, scan, score)

            scans.append(scan)
            scores.append(score)
            reviews.append(review)

            if export:
                self._export_repo_bundle(
                    owner=owner,
                    repo=repo,
                    scan=scan,
                    score=score,
                    review=review,
                )

        ranking = self.ranker.build_ranking(repos=repos, scores=scores, reviews=reviews)
        selection = self.selector.select(ranking)

        artifacts = AuditArtifacts(
            repos=repos,
            clone_results=clone_results,
            scans=scans,
            scores=scores,
            reviews=reviews,
            ranking=ranking,
            selection=selection,
        )

        if export:
            self.export_aggregate_artifacts(owner=owner, artifacts=artifacts)

        return artifacts

    def scan_repo(self, repo: RepoMetadata, local_path: Path) -> RepoScanResult:
        scan_result = RepoScanResult(
            repo_name=repo.name,
            repo_full_name=repo.full_name,
            local_path=str(local_path),
        )

        for scanner in self.scanners:
            summary = scanner.scan(repo, local_path, scan_result)
            scan_result.add_scanner_summary(summary)

        return scan_result

    def export_aggregate_artifacts(
        self,
        *,
        owner: str,
        artifacts: AuditArtifacts,
    ) -> None:
        base_dir = self.settings.processed_dir / owner
        base_dir.mkdir(parents=True, exist_ok=True)

        JsonExporter.export_repo_metadata_list(
            base_dir / "repos_metadata.json",
            artifacts.repos,
        )
        JsonExporter.export_scans(
            base_dir / "repo_scans.json",
            artifacts.scans,
        )
        JsonExporter.export_scores(
            base_dir / "repo_scores.json",
            artifacts.scores,
        )
        JsonExporter.export_reviews(
            base_dir / "repo_reviews.json",
            artifacts.reviews,
        )

        CsvExporter.export_repo_inventory(
            base_dir / "repo_inventory.csv",
            artifacts.repos,
        )
        CsvExporter.export_scores_table(
            base_dir / "repo_scores.csv",
            artifacts.scores,
        )
        CsvExporter.export_reviews_table(
            base_dir / "repo_reviews.csv",
            artifacts.reviews,
        )
        CsvExporter.export_master_table(
            base_dir / "portfolio_master_table.csv",
            repos=artifacts.repos,
            scores=artifacts.scores,
            reviews=artifacts.reviews,
        )

        if artifacts.ranking is not None:
            JsonExporter._write_json(base_dir / "ranking_summary.json", artifacts.ranking.to_dict())
            JsonExporter._write_json(
                base_dir / "ranking.json",
                [item.to_dict() for item in artifacts.ranking.ranked_repos],
            )
            JsonExporter._write_json(
                base_dir / "redundancy_analysis.json",
                artifacts.ranking.redundancy_analysis.to_dict(),
            )

        if artifacts.selection is not None:
            JsonExporter._write_json(
                base_dir / "portfolio_selection.json",
                artifacts.selection.to_dict(),
            )

        if artifacts.ranking is not None and artifacts.selection is not None:
            site_payload = build_site_payload(
                owner=owner,
                ranking=artifacts.ranking,
                selection=artifacts.selection,
            )
            JsonExporter._write_json(
                base_dir / "site_payload.json",
                site_payload.model_dump(mode="json"),
            )
            JsonExporter._write_json(
                base_dir / "repos_site_data.json",
                site_payload.model_dump(mode="json"),
            )

    def _export_repo_bundle(
        self,
        *,
        owner: str,
        repo: RepoMetadata,
        scan: RepoScanResult,
        score: RepoScore,
        review: RepoReview,
    ) -> None:
        bundle_dir = self.settings.interim_dir / "bundles" / owner
        bundle_dir.mkdir(parents=True, exist_ok=True)
        output_path = bundle_dir / f"{repo.full_name.replace('/', '__')}.json"

        JsonExporter.export_repo_bundle(
            output_path,
            repo=repo,
            scan=scan,
            score=score,
            review=review,
        )