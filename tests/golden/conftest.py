from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from portfolio_auditor.ranking.portfolio_selection import PortfolioSelector
from portfolio_auditor.ranking.ranker import Ranker, RankingSummary
from portfolio_auditor.reviewing.deterministic_review import DeterministicReviewer
from portfolio_auditor.scoring.engine import ScoringEngine
from tests.golden.fixtures.scenario_builders import GoldenPortfolioCase, build_golden_portfolio_case

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"


@pytest.fixture
def golden_case() -> GoldenPortfolioCase:
    return build_golden_portfolio_case()


@pytest.fixture
def scoring_engine() -> ScoringEngine:
    return ScoringEngine()


@pytest.fixture
def reviewer() -> DeterministicReviewer:
    return DeterministicReviewer()


@pytest.fixture
def ranker() -> Ranker:
    return Ranker()


@pytest.fixture
def selector() -> PortfolioSelector:
    return PortfolioSelector()


@pytest.fixture
def scored_repositories(
    golden_case: GoldenPortfolioCase,
    scoring_engine: ScoringEngine,
) -> list[dict[str, Any]]:
    return [
        {
            "repo": repo,
            "scan": scan,
            "score": scoring_engine.score(repo, scan),
        }
        for repo, scan in zip(golden_case.repos, golden_case.scans, strict=True)
    ]


@pytest.fixture
def reviewed_repositories(
    reviewer: DeterministicReviewer,
    scored_repositories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            **item,
            "review": reviewer.review(item["repo"], item["scan"], item["score"]),
        }
        for item in scored_repositories
    ]


@pytest.fixture
def ranking_summary(
    ranker: Ranker,
    golden_case: GoldenPortfolioCase,
    reviewed_repositories: list[dict[str, Any]],
) -> RankingSummary:
    return ranker.build_ranking(
        repos=golden_case.repos,
        scores=[item["score"] for item in reviewed_repositories],
        reviews=[item["review"] for item in reviewed_repositories],
    )


@pytest.fixture
def selection_result(
    selector: PortfolioSelector,
    ranking_summary: RankingSummary,
):
    return selector.select(ranking_summary)



def load_snapshot(name: str) -> Any:
    with (SNAPSHOT_DIR / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)



def assert_matches_snapshot(snapshot_name: str, actual: Any) -> None:
    expected = load_snapshot(snapshot_name)
    assert actual == expected
