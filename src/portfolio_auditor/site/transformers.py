from __future__ import annotations

from portfolio_auditor.ranking.portfolio_selection import PortfolioSelection
from portfolio_auditor.ranking.ranker import RankedRepo, RankingSummary
from portfolio_auditor.site.api_schema import (
    SitePayload,
    SitePortfolioBucket,
    SitePortfolioOverview,
    SiteRepositoryCard,
)


def ranked_repo_to_site_card(repo: RankedRepo) -> SiteRepositoryCard:
    return SiteRepositoryCard.model_validate(repo.to_dict())


def ranking_to_site_cards(ranking: RankingSummary) -> list[SiteRepositoryCard]:
    return [ranked_repo_to_site_card(repo) for repo in ranking.ranked_repos]


def build_site_payload(
    *,
    owner: str,
    ranking: RankingSummary,
    selection: PortfolioSelection,
) -> SitePayload:
    cards = ranking_to_site_cards(ranking)
    overview = SitePortfolioOverview(
        total_repositories=len(ranking.ranked_repos),
        featured_count=len(selection.featured_repos),
        keep_visible_but_improve_count=len(selection.keep_visible_but_improve),
        improvement_backlog_count=len(selection.improvement_backlog),
        archive_candidates_count=len(selection.archive_candidates),
        private_candidates_count=len(selection.private_candidates),
        redundancy_candidates_count=len(selection.redundancy_candidates),
        overlap_clusters_count=len(ranking.redundancy_analysis.overlap_clusters),
        manager_summary=selection.manager_summary,
        decision_buckets=[
            SitePortfolioBucket(
                label="FEATURE_NOW",
                count=len(ranking.feature_now),
                repos=[repo.repo_full_name for repo in ranking.feature_now],
            ),
            SitePortfolioBucket(
                label="KEEP_AND_IMPROVE",
                count=len(ranking.keep_and_improve),
                repos=[repo.repo_full_name for repo in ranking.keep_and_improve],
            ),
            SitePortfolioBucket(
                label="MERGE_OR_REPOSITION",
                count=len(ranking.merge_or_reposition),
                repos=[repo.repo_full_name for repo in ranking.merge_or_reposition],
            ),
            SitePortfolioBucket(
                label="ARCHIVE_PUBLIC",
                count=len(ranking.archive_public),
                repos=[repo.repo_full_name for repo in ranking.archive_public],
            ),
            SitePortfolioBucket(
                label="MAKE_PRIVATE",
                count=len(ranking.make_private),
                repos=[repo.repo_full_name for repo in ranking.make_private],
            ),
        ],
    )
    return SitePayload(
        generated_for_owner=owner,
        overview=overview,
        repositories=cards,
    )