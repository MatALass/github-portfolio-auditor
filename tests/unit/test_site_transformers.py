from portfolio_auditor.models.portfolio_decision import PortfolioDecision
from portfolio_auditor.ranking.deduplication import RedundancyAnalysis
from portfolio_auditor.ranking.portfolio_selection import PortfolioSelector
from portfolio_auditor.ranking.ranker import RankedRepo, RankingSummary
from portfolio_auditor.site.transformers import build_site_payload


def ranked_repo(rank: int, name: str, decision: PortfolioDecision, score: float) -> RankedRepo:
    return RankedRepo(
        rank=rank,
        repo_full_name=f"user/{name}",
        repo_name=name,
        global_score=score,
        score_label="good",
        confidence=0.82,
        portfolio_decision=decision.value,
        primary_language="Python",
        description=f"{name} description",
        owner_login="user",
        html_url=f"https://github.com/user/{name}",
        homepage=None,
        strengths_count=2,
        weaknesses_count=1,
        blockers_count=0,
        priority_actions_count=2,
        stars=1,
        forks=0,
        overlap_cluster_id=None,
        overlap_candidate_count=0,
        strongest_overlap_score=0.0,
        redundancy_status="UNIQUE",
        redundancy_reason=None,
        representative_repo_full_name=None,
    )


def test_build_site_payload_creates_valid_summary() -> None:
    repos = [
        ranked_repo(1, "alpha", PortfolioDecision.FEATURE_NOW, 90),
        ranked_repo(2, "beta", PortfolioDecision.KEEP_AND_IMPROVE, 72),
    ]
    ranking = RankingSummary(
        ranked_repos=repos,
        feature_now=[repos[0]],
        keep_and_improve=[repos[1]],
        merge_or_reposition=[],
        archive_public=[],
        make_private=[],
        top_repos=repos,
        worst_repos=list(reversed(repos)),
        highest_priority_improvements=[repos[1]],
        redundancy_analysis=RedundancyAnalysis(overlap_pairs=[], overlap_clusters=[], repo_statuses={}),
    )
    selection = PortfolioSelector().select(ranking)

    payload = build_site_payload(owner="user", ranking=ranking, selection=selection)

    assert payload.generated_for_owner == "user"
    assert payload.overview.total_repositories == 2
    assert payload.overview.featured_count == 1
    assert payload.overview.redundancy_candidates_count == 0
    assert payload.repositories[0].repo_full_name == "user/alpha"
    assert payload.repositories[1].portfolio_decision == "KEEP_AND_IMPROVE"