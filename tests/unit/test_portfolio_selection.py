from portfolio_auditor.models.portfolio_decision import PortfolioDecision
from portfolio_auditor.ranking.deduplication import RedundancyAnalysis
from portfolio_auditor.ranking.portfolio_selection import PortfolioSelector
from portfolio_auditor.ranking.ranker import RankedRepo, RankingSummary


def ranked_repo(
    rank: int,
    name: str,
    decision: PortfolioDecision,
    score: float,
    actions: int,
    blockers: int = 0,
    redundancy_status: str = "UNIQUE",
    strongest_overlap_score: float = 0.0,
    representative: str | None = None,
) -> RankedRepo:
    return RankedRepo(
        rank=rank,
        repo_full_name=f"user/{name}",
        repo_name=name,
        global_score=score,
        score_label="strong",
        confidence=0.9,
        portfolio_decision=decision.value,
        primary_language="Python",
        description=f"{name} description",
        owner_login="user",
        html_url=f"https://github.com/user/{name}",
        homepage=None,
        strengths_count=3,
        weaknesses_count=2,
        blockers_count=blockers,
        priority_actions_count=actions,
        stars=0,
        forks=0,
        overlap_cluster_id="cluster_001" if redundancy_status != "UNIQUE" else None,
        overlap_candidate_count=1 if redundancy_status != "UNIQUE" else 0,
        strongest_overlap_score=strongest_overlap_score,
        redundancy_status=redundancy_status,
        redundancy_reason=None,
        representative_repo_full_name=representative,
    )


def test_selector_builds_expected_buckets() -> None:
    repos = [
        ranked_repo(1, "best", PortfolioDecision.FEATURE_NOW, 91, 1),
        ranked_repo(2, "solid", PortfolioDecision.KEEP_AND_IMPROVE, 76, 3),
        ranked_repo(
            3,
            "merge-me",
            PortfolioDecision.MERGE_OR_REPOSITION,
            58,
            4,
            blockers=1,
            redundancy_status="OVERLAP_CANDIDATE",
            strongest_overlap_score=0.83,
            representative="user/best",
        ),
        ranked_repo(4, "archive-me", PortfolioDecision.ARCHIVE_PUBLIC, 40, 2),
        ranked_repo(5, "private-me", PortfolioDecision.MAKE_PRIVATE, 22, 5, blockers=2),
    ]
    ranking = RankingSummary(
        ranked_repos=repos,
        feature_now=[repos[0]],
        keep_and_improve=[repos[1]],
        merge_or_reposition=[repos[2]],
        archive_public=[repos[3]],
        make_private=[repos[4]],
        top_repos=repos[:3],
        worst_repos=repos[-2:],
        highest_priority_improvements=[repos[1], repos[2]],
        redundancy_analysis=RedundancyAnalysis(overlap_pairs=[], overlap_clusters=[], repo_statuses={}),
    )

    selection = PortfolioSelector().select(ranking)

    assert [repo.repo_name for repo in selection.featured_repos] == ["best"]
    assert [repo.repo_name for repo in selection.keep_visible_but_improve] == ["solid"]
    assert [repo.repo_name for repo in selection.improvement_backlog][:2] == ["merge-me", "solid"]
    assert [repo.repo_name for repo in selection.archive_candidates] == ["archive-me"]
    assert [repo.repo_name for repo in selection.private_candidates] == ["private-me"]
    assert [repo.repo_name for repo in selection.redundancy_candidates] == ["merge-me"]
    assert "Redundancy candidates: 1." in selection.manager_summary