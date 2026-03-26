from __future__ import annotations

from dataclasses import dataclass

from portfolio_auditor.models.portfolio_decision import PortfolioDecision
from portfolio_auditor.ranking.ranker import RankedRepo, RankingSummary


@dataclass(slots=True, frozen=True)
class PortfolioSelection:
    """
    Strategic portfolio selection outputs built from ranked repositories.
    """

    featured_repos: list[RankedRepo]
    keep_visible_but_improve: list[RankedRepo]
    improvement_backlog: list[RankedRepo]
    archive_candidates: list[RankedRepo]
    private_candidates: list[RankedRepo]
    redundancy_candidates: list[RankedRepo]
    manager_summary: str

    def to_dict(self) -> dict:
        return {
            "featured_repos": [repo.to_dict() for repo in self.featured_repos],
            "keep_visible_but_improve": [repo.to_dict() for repo in self.keep_visible_but_improve],
            "improvement_backlog": [repo.to_dict() for repo in self.improvement_backlog],
            "archive_candidates": [repo.to_dict() for repo in self.archive_candidates],
            "private_candidates": [repo.to_dict() for repo in self.private_candidates],
            "redundancy_candidates": [repo.to_dict() for repo in self.redundancy_candidates],
            "manager_summary": self.manager_summary,
        }


class PortfolioSelector:
    """
    Translate ranking outputs into a portfolio strategy.

    V2 adds explicit redundancy candidates so the portfolio can avoid showcasing
    several repositories that tell essentially the same story.
    """

    def select(self, ranking: RankingSummary) -> PortfolioSelection:
        featured_repos = self._limit(
            [
                repo
                for repo in ranking.ranked_repos
                if repo.portfolio_decision == PortfolioDecision.FEATURE_NOW.value
                and repo.redundancy_status != "OVERLAP_CANDIDATE"
            ],
            8,
        )

        keep_visible_but_improve = self._limit(
            [
                repo
                for repo in ranking.ranked_repos
                if repo.portfolio_decision == PortfolioDecision.KEEP_AND_IMPROVE.value
            ],
            12,
        )

        improvement_backlog = self._build_improvement_backlog(ranking)
        redundancy_candidates = self._build_redundancy_candidates(ranking)

        archive_candidates = [
            repo
            for repo in ranking.ranked_repos
            if repo.portfolio_decision == PortfolioDecision.ARCHIVE_PUBLIC.value
        ]

        private_candidates = [
            repo
            for repo in ranking.ranked_repos
            if repo.portfolio_decision == PortfolioDecision.MAKE_PRIVATE.value
        ]

        manager_summary = self._build_manager_summary(
            featured_repos=featured_repos,
            keep_visible_but_improve=keep_visible_but_improve,
            improvement_backlog=improvement_backlog,
            archive_candidates=archive_candidates,
            private_candidates=private_candidates,
            redundancy_candidates=redundancy_candidates,
            total_count=len(ranking.ranked_repos),
            cluster_count=len(ranking.redundancy_analysis.overlap_clusters),
        )

        return PortfolioSelection(
            featured_repos=featured_repos,
            keep_visible_but_improve=keep_visible_but_improve,
            improvement_backlog=improvement_backlog,
            archive_candidates=archive_candidates,
            private_candidates=private_candidates,
            redundancy_candidates=redundancy_candidates,
            manager_summary=manager_summary,
        )

    @staticmethod
    def _limit(items: list[RankedRepo], limit: int) -> list[RankedRepo]:
        return items[:limit]

    @staticmethod
    def _build_improvement_backlog(ranking: RankingSummary) -> list[RankedRepo]:
        candidates = [
            repo
            for repo in ranking.ranked_repos
            if repo.portfolio_decision
            in {
                PortfolioDecision.KEEP_AND_IMPROVE.value,
                PortfolioDecision.MERGE_OR_REPOSITION.value,
            }
        ]

        candidates.sort(
            key=lambda item: (
                item.redundancy_status != "OVERLAP_CANDIDATE",
                item.portfolio_decision != PortfolioDecision.KEEP_AND_IMPROVE.value,
                -(item.priority_actions_count),
                -(item.strongest_overlap_score),
                -(item.global_score),
                item.repo_name.lower(),
            )
        )
        return candidates[:15]

    @staticmethod
    def _build_redundancy_candidates(ranking: RankingSummary) -> list[RankedRepo]:
        candidates = [
            repo for repo in ranking.ranked_repos if repo.redundancy_status == "OVERLAP_CANDIDATE"
        ]
        candidates.sort(
            key=lambda item: (
                -(item.strongest_overlap_score),
                -(item.overlap_candidate_count),
                item.rank,
            )
        )
        return candidates[:15]

    @staticmethod
    def _build_manager_summary(
        *,
        featured_repos: list[RankedRepo],
        keep_visible_but_improve: list[RankedRepo],
        improvement_backlog: list[RankedRepo],
        archive_candidates: list[RankedRepo],
        private_candidates: list[RankedRepo],
        redundancy_candidates: list[RankedRepo],
        total_count: int,
        cluster_count: int,
    ) -> str:
        featured_count = len(featured_repos)
        visible_improve_count = len(keep_visible_but_improve)
        backlog_count = len(improvement_backlog)
        archive_count = len(archive_candidates)
        private_count = len(private_candidates)
        redundancy_count = len(redundancy_candidates)

        if featured_count == 0 and visible_improve_count == 0:
            headline = (
                "The current GitHub portfolio does not yet contain strong repositories ready to be highlighted."
            )
        elif featured_count <= 3:
            headline = (
                "The portfolio contains a limited number of strong repositories and still needs targeted consolidation."
            )
        else:
            headline = (
                "The portfolio already contains several credible repositories, with additional improvement opportunities."
            )

        return (
            f"{headline} Total repositories analyzed: {total_count}. "
            f"Featured now: {featured_count}. "
            f"Keep visible but improve: {visible_improve_count}. "
            f"Improvement backlog: {backlog_count}. "
            f"Redundancy candidates: {redundancy_count}. "
            f"Overlap clusters detected: {cluster_count}. "
            f"Archive candidates: {archive_count}. "
            f"Private candidates: {private_count}."
        )