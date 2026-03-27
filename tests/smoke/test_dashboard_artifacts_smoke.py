from __future__ import annotations

import json
from pathlib import Path

from portfolio_auditor.dashboard import data_loader


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_load_dashboard_data_smoke(monkeypatch, tmp_path: Path) -> None:
    processed_dir = tmp_path / "processed"
    owner_dir = processed_dir / "sample-owner"
    owner_dir.mkdir(parents=True, exist_ok=True)

    ranking = [
        {
            "rank": 1,
            "repo_name": "repo-alpha",
            "repo_full_name": "sample-owner/repo-alpha",
            "global_score": 84.5,
            "confidence": 0.88,
            "stars": 3,
            "forks": 1,
            "primary_language": "Python",
            "portfolio_decision": "FEATURE_NOW",
            "redundancy_status": "UNIQUE",
            "overlap_cluster_id": None,
            "priority_actions_count": 2,
            "homepage": "https://example.com/repo-alpha",
            "description": "Main portfolio repository.",
        },
        {
            "rank": 2,
            "repo_name": "repo-beta",
            "repo_full_name": "sample-owner/repo-beta",
            "global_score": 67.0,
            "confidence": 0.76,
            "stars": 0,
            "forks": 0,
            "primary_language": "Python",
            "portfolio_decision": "KEEP_AND_IMPROVE",
            "redundancy_status": "OVERLAP_MEMBER",
            "overlap_cluster_id": "cluster-1",
            "priority_actions_count": 1,
            "homepage": "",
            "description": "",
        },
    ]

    ranking_summary = {
        "owner": "sample-owner",
        "repo_count": 2,
    }

    portfolio_selection = {
        "featured_repos": [
            {
                "repo_full_name": "sample-owner/repo-alpha",
            }
        ],
        "keep_visible_but_improve": [
            {
                "repo_full_name": "sample-owner/repo-beta",
            }
        ],
        "improvement_backlog": [],
        "archive_candidates": [],
        "private_candidates": [],
        "redundancy_candidates": [],
    }

    redundancy_analysis = {
        "overlap_pairs": [
            {
                "repo_a": "sample-owner/repo-alpha",
                "repo_b": "sample-owner/repo-beta",
                "score": 0.41,
            }
        ],
        "overlap_clusters": [
            {
                "cluster_id": "cluster-1",
                "repos": ["sample-owner/repo-alpha", "sample-owner/repo-beta"],
            }
        ],
        "repo_statuses": {
            "sample-owner/repo-alpha": "UNIQUE",
            "sample-owner/repo-beta": "OVERLAP_MEMBER",
        },
    }

    site_payload = {
        "overview": {
            "manager_summary": "Smoke-test portfolio summary.",
        }
    }

    repos_site_data = {
        "repos": [
            {"repo_name": "repo-alpha"},
            {"repo_name": "repo-beta"},
        ]
    }

    repo_reviews = [
        {
            "repo_name": "repo-alpha",
            "quick_wins": [{"text": "Tighten CI setup."}],
            "blockers": [],
            "priority_actions": [
                {"text": "Run automated tests in CI.", "priority": "high"},
                {"text": "Document exactly how to run and use the project.", "priority": "medium"},
            ],
        },
        {
            "repo_name": "repo-beta",
            "quick_wins": [{"text": "Add a concise GitHub description."}],
            "blockers": [{"text": "README is weak."}],
            "priority_actions": [
                {"text": "Add a concise GitHub description.", "priority": "medium"},
            ],
        },
    ]

    repo_scores = [
        {
            "repo_name": "repo-alpha",
            "breakdown": {
                "architecture_structure": 18.0,
                "documentation_delivery": 15.0,
                "testing_reliability": 16.0,
                "technical_depth": 12.0,
                "portfolio_relevance": 13.0,
                "maintainability_cleanliness": 10.5,
            },
            "penalties": [
                {"code": "NO_TEST_CI", "points": 3.0},
            ],
        },
        {
            "repo_name": "repo-beta",
            "breakdown": {
                "architecture_structure": 14.0,
                "documentation_delivery": 10.0,
                "testing_reliability": 11.0,
                "technical_depth": 10.0,
                "portfolio_relevance": 12.0,
                "maintainability_cleanliness": 10.0,
            },
            "penalties": [],
        },
    ]

    repo_scans = [
        {
            "repo_name": "repo-alpha",
            "issues": [{"code": "NO_TEST_CI"}],
        },
        {
            "repo_name": "repo-beta",
            "issues": [{"code": "README_TOO_SHORT"}],
        },
    ]

    _write_json(owner_dir / "ranking.json", ranking)
    _write_json(owner_dir / "ranking_summary.json", ranking_summary)
    _write_json(owner_dir / "portfolio_selection.json", portfolio_selection)
    _write_json(owner_dir / "redundancy_analysis.json", redundancy_analysis)
    _write_json(owner_dir / "site_payload.json", site_payload)
    _write_json(owner_dir / "repos_site_data.json", repos_site_data)
    _write_json(owner_dir / "repo_reviews.json", repo_reviews)
    _write_json(owner_dir / "repo_scores.json", repo_scores)
    _write_json(owner_dir / "repo_scans.json", repo_scans)

    monkeypatch.setattr(data_loader, "PROCESSED_DIR", processed_dir)
    monkeypatch.setattr(data_loader, "_build_comparison", lambda current_df, owner: (None, None))

    data = data_loader.load_dashboard_data("sample-owner")

    assert data.owner == "sample-owner"
    assert not data.repo_df.empty
    assert list(data.repo_df["repo_name"]) == ["repo-alpha", "repo-beta"]
    assert data.overview_metrics["total_repositories"] == 2
    assert data.overview_metrics["highlight_count"] == 1
    assert data.optimizer_summary["current_quality"] > 0
    assert data.next_actions
    assert data.comparison_summary is None