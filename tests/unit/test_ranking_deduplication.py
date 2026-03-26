from portfolio_auditor.models.portfolio_decision import PortfolioDecision
from portfolio_auditor.models.repo_metadata import (
    RepoEngagement,
    RepoFlags,
    RepoLanguageStats,
    RepoLinks,
    RepoMetadata,
    RepoOwner,
    RepoTimestamps,
    RepoTopics,
)
from portfolio_auditor.models.repo_review import RepoReview
from portfolio_auditor.models.repo_score import RepoScore
from portfolio_auditor.ranking.ranker import Ranker


def build_repo(name: str, description: str, topics: list[str]) -> RepoMetadata:
    return RepoMetadata(
        id=abs(hash(name)) % 100000 + 1,
        name=name,
        full_name=f"user/{name}",
        description=description,
        default_branch="main",
        size_kb=100,
        owner=RepoOwner(login="user", type="User", html_url="https://github.com/user"),
        flags=RepoFlags(),
        engagement=RepoEngagement(stargazers_count=1),
        timestamps=RepoTimestamps(
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-02T00:00:00Z",
            pushed_at="2025-01-03T00:00:00Z",
        ),
        links=RepoLinks(
            html_url=f"https://github.com/user/{name}",
            clone_url=f"https://github.com/user/{name}.git",
        ),
        language="Python",
        language_stats=RepoLanguageStats(languages={"Python": 1000}),
        topics=RepoTopics(items=topics),
    )


def build_score(repo_name: str, score: float) -> RepoScore:
    return RepoScore(
        repo_name=repo_name,
        repo_full_name=f"user/{repo_name}",
        global_score=score,
        confidence=0.9,
    )


def build_review(repo_name: str, decision: PortfolioDecision) -> RepoReview:
    review = RepoReview(
        repo_name=repo_name,
        repo_full_name=f"user/{repo_name}",
        portfolio_decision=decision,
        executive_summary="summary",
    )
    review.add_strength("Strong structure")
    review.add_priority_action("Improve README")
    return review


def test_ranker_detects_overlap_and_marks_representative() -> None:
    repos = [
        build_repo(
            "footpredict-pl",
            "Premier League football match prediction dashboard with betting-oriented analysis.",
            ["football", "prediction", "streamlit"],
        ),
        build_repo(
            "ml-football-predictor",
            "Football match prediction dashboard focused on league betting analysis and forecasts.",
            ["football", "prediction", "dashboard"],
        ),
        build_repo(
            "supply-chain-optimizer",
            "Supply chain optimization experiments for warehouse routing.",
            ["optimization", "operations-research"],
        ),
    ]
    scores = [
        build_score("footpredict-pl", 81.0),
        build_score("ml-football-predictor", 74.0),
        build_score("supply-chain-optimizer", 79.0),
    ]
    reviews = [
        build_review("footpredict-pl", PortfolioDecision.FEATURE_NOW),
        build_review("ml-football-predictor", PortfolioDecision.KEEP_AND_IMPROVE),
        build_review("supply-chain-optimizer", PortfolioDecision.FEATURE_NOW),
    ]

    ranking = Ranker().build_ranking(repos=repos, scores=scores, reviews=reviews)

    assert len(ranking.redundancy_analysis.overlap_clusters) == 1
    statuses = ranking.redundancy_analysis.repo_statuses
    assert statuses["user/footpredict-pl"].redundancy_status == "REPRESENTATIVE"
    assert statuses["user/ml-football-predictor"].redundancy_status == "OVERLAP_CANDIDATE"
    assert "user/supply-chain-optimizer" not in statuses

    ranked_index = {repo.repo_full_name: repo for repo in ranking.ranked_repos}
    assert ranked_index["user/ml-football-predictor"].overlap_cluster_id is not None
    assert ranked_index["user/ml-football-predictor"].representative_repo_full_name == "user/footpredict-pl"