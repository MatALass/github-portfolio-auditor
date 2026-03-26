from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from portfolio_auditor.models.portfolio_decision import PortfolioDecision
from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_review import RepoReview
from portfolio_auditor.models.repo_score import RepoScore
from portfolio_auditor.ranking.deduplication import RedundancyAnalysis, RedundancyDetector


@dataclass(slots=True, frozen=True)
class RankedRepo:
    """
    Global ranked representation of a repository enriched with portfolio overlap signals.
    """

    rank: int
    repo_full_name: str
    repo_name: str
    global_score: float
    score_label: str
    confidence: float
    portfolio_decision: str
    primary_language: str | None
    description: str | None
    owner_login: str
    html_url: str
    homepage: str | None
    strengths_count: int
    weaknesses_count: int
    blockers_count: int
    priority_actions_count: int
    stars: int
    forks: int
    overlap_cluster_id: str | None
    overlap_candidate_count: int
    strongest_overlap_score: float
    redundancy_status: str
    redundancy_reason: str | None
    representative_repo_full_name: str | None

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "repo_full_name": self.repo_full_name,
            "repo_name": self.repo_name,
            "global_score": self.global_score,
            "score_label": self.score_label,
            "confidence": self.confidence,
            "portfolio_decision": self.portfolio_decision,
            "primary_language": self.primary_language,
            "description": self.description,
            "owner_login": self.owner_login,
            "html_url": self.html_url,
            "homepage": self.homepage,
            "strengths_count": self.strengths_count,
            "weaknesses_count": self.weaknesses_count,
            "blockers_count": self.blockers_count,
            "priority_actions_count": self.priority_actions_count,
            "stars": self.stars,
            "forks": self.forks,
            "overlap_cluster_id": self.overlap_cluster_id,
            "overlap_candidate_count": self.overlap_candidate_count,
            "strongest_overlap_score": self.strongest_overlap_score,
            "redundancy_status": self.redundancy_status,
            "redundancy_reason": self.redundancy_reason,
            "representative_repo_full_name": self.representative_repo_full_name,
        }


@dataclass(slots=True, frozen=True)
class RankingSummary:
    """
    Aggregated ranking outputs for downstream reporting and dashboarding.
    """

    ranked_repos: list[RankedRepo]
    feature_now: list[RankedRepo]
    keep_and_improve: list[RankedRepo]
    merge_or_reposition: list[RankedRepo]
    archive_public: list[RankedRepo]
    make_private: list[RankedRepo]
    top_repos: list[RankedRepo]
    worst_repos: list[RankedRepo]
    highest_priority_improvements: list[RankedRepo]
    redundancy_analysis: RedundancyAnalysis

    def to_dict(self) -> dict:
        return {
            "ranked_repos": [item.to_dict() for item in self.ranked_repos],
            "feature_now": [item.to_dict() for item in self.feature_now],
            "keep_and_improve": [item.to_dict() for item in self.keep_and_improve],
            "merge_or_reposition": [item.to_dict() for item in self.merge_or_reposition],
            "archive_public": [item.to_dict() for item in self.archive_public],
            "make_private": [item.to_dict() for item in self.make_private],
            "top_repos": [item.to_dict() for item in self.top_repos],
            "worst_repos": [item.to_dict() for item in self.worst_repos],
            "highest_priority_improvements": [
                item.to_dict() for item in self.highest_priority_improvements
            ],
            "redundancy_analysis": self.redundancy_analysis.to_dict(),
        }


class Ranker:
    """
    Build a global ranking from repo metadata, scores, and reviews.

    V2 enriches ranking with deterministic redundancy detection so that the
    portfolio can favor representative repositories instead of rewarding many
    near-duplicates.
    """

    def __init__(self) -> None:
        self.redundancy_detector = RedundancyDetector()

    def build_ranking(
        self,
        *,
        repos: list[RepoMetadata],
        scores: list[RepoScore],
        reviews: list[RepoReview],
    ) -> RankingSummary:
        repo_index = {repo.full_name: repo for repo in repos}
        score_index = {score.repo_full_name: score for score in scores}
        review_index = {review.repo_full_name: review for review in reviews}

        common_full_names = sorted(
            set(repo_index.keys()) & set(score_index.keys()) & set(review_index.keys())
        )

        redundancy_analysis = self.redundancy_detector.analyze(
            repos=repos,
            scores=scores,
            reviews=reviews,
        )

        ranked_rows = [
            self._build_rank_candidate(
                repo=repo_index[full_name],
                score=score_index[full_name],
                review=review_index[full_name],
                redundancy_analysis=redundancy_analysis,
            )
            for full_name in common_full_names
        ]

        ranked_rows.sort(
            key=lambda item: (
                -item["ranking_value"],
                -item["score"].global_score,
                -item["score"].confidence,
                item["repo"].name.lower(),
            )
        )

        ranked_repos: list[RankedRepo] = []
        for index, item in enumerate(ranked_rows, start=1):
            ranked_repos.append(
                self._to_ranked_repo(
                    rank=index,
                    repo=item["repo"],
                    score=item["score"],
                    review=item["review"],
                    redundancy_analysis=redundancy_analysis,
                )
            )

        feature_now = self._filter_by_decision(ranked_repos, PortfolioDecision.FEATURE_NOW)
        keep_and_improve = self._filter_by_decision(
            ranked_repos, PortfolioDecision.KEEP_AND_IMPROVE
        )
        merge_or_reposition = self._filter_by_decision(
            ranked_repos, PortfolioDecision.MERGE_OR_REPOSITION
        )
        archive_public = self._filter_by_decision(ranked_repos, PortfolioDecision.ARCHIVE_PUBLIC)
        make_private = self._filter_by_decision(ranked_repos, PortfolioDecision.MAKE_PRIVATE)

        top_repos = ranked_repos[:10]
        worst_repos = list(sorted(ranked_repos, key=lambda item: item.global_score))[:10]
        highest_priority_improvements = self._build_priority_improvements(ranked_repos)

        return RankingSummary(
            ranked_repos=ranked_repos,
            feature_now=feature_now,
            keep_and_improve=keep_and_improve,
            merge_or_reposition=merge_or_reposition,
            archive_public=archive_public,
            make_private=make_private,
            top_repos=top_repos,
            worst_repos=worst_repos,
            highest_priority_improvements=highest_priority_improvements,
            redundancy_analysis=redundancy_analysis,
        )

    def _build_rank_candidate(
        self,
        *,
        repo: RepoMetadata,
        score: RepoScore,
        review: RepoReview,
        redundancy_analysis: RedundancyAnalysis,
    ) -> dict:
        decision_bonus = self._decision_bonus(review.portfolio_decision)
        confidence_bonus = score.confidence * 2.0
        blocker_penalty = min(6.0, len(review.blockers) * 1.25)
        redundancy_penalty = self._redundancy_penalty(
            redundancy_analysis.status_for(repo.full_name)
        )

        ranking_value = (
            score.global_score
            + decision_bonus
            + confidence_bonus
            - blocker_penalty
            - redundancy_penalty
        )

        return {
            "repo": repo,
            "score": score,
            "review": review,
            "ranking_value": round(ranking_value, 4),
        }

    @staticmethod
    def _decision_bonus(decision: PortfolioDecision) -> float:
        if decision == PortfolioDecision.FEATURE_NOW:
            return 6.0
        if decision == PortfolioDecision.KEEP_AND_IMPROVE:
            return 2.5
        if decision == PortfolioDecision.MERGE_OR_REPOSITION:
            return -1.0
        if decision == PortfolioDecision.ARCHIVE_PUBLIC:
            return -4.0
        if decision == PortfolioDecision.MAKE_PRIVATE:
            return -8.0
        return 0.0

    @staticmethod
    def _redundancy_penalty(status) -> float:
        if status.redundancy_status == "OVERLAP_CANDIDATE":
            if status.strongest_overlap_score >= 0.72:
                return 6.0
            return 3.0
        return 0.0

    @staticmethod
    def _to_ranked_repo(
        *,
        rank: int,
        repo: RepoMetadata,
        score: RepoScore,
        review: RepoReview,
        redundancy_analysis: RedundancyAnalysis,
    ) -> RankedRepo:
        overlap_status = redundancy_analysis.status_for(repo.full_name)
        return RankedRepo(
            rank=rank,
            repo_full_name=repo.full_name,
            repo_name=repo.name,
            global_score=score.global_score,
            score_label=score.score_label,
            confidence=score.confidence,
            portfolio_decision=review.portfolio_decision.value,
            primary_language=repo.language or repo.language_stats.primary_language,
            description=repo.description,
            owner_login=repo.owner.login,
            html_url=str(repo.links.html_url),
            homepage=str(repo.links.homepage) if repo.links.homepage else None,
            strengths_count=len(review.strengths),
            weaknesses_count=len(review.weaknesses),
            blockers_count=len(review.blockers),
            priority_actions_count=len(review.priority_actions),
            stars=repo.engagement.stargazers_count,
            forks=repo.engagement.forks_count,
            overlap_cluster_id=overlap_status.cluster_id,
            overlap_candidate_count=overlap_status.overlap_candidate_count,
            strongest_overlap_score=overlap_status.strongest_overlap_score,
            redundancy_status=overlap_status.redundancy_status,
            redundancy_reason=overlap_status.redundancy_reason,
            representative_repo_full_name=overlap_status.representative_repo_full_name,
        )

    @staticmethod
    def _filter_by_decision(
        ranked_repos: Iterable[RankedRepo],
        decision: PortfolioDecision,
    ) -> list[RankedRepo]:
        return [repo for repo in ranked_repos if repo.portfolio_decision == decision.value]

    @staticmethod
    def _build_priority_improvements(ranked_repos: list[RankedRepo]) -> list[RankedRepo]:
        candidates = [
            repo
            for repo in ranked_repos
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
        return candidates[:10]