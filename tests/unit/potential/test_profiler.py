from __future__ import annotations

from datetime import UTC, datetime

import pytest

from portfolio_auditor.collectors.local.collector import LocalCollector, LocalRepoEntry
from portfolio_auditor.potential.profiler import RepoProfiler, count_figures, count_keyword

from .conftest import make_git_repo

pytestmark = pytest.mark.unit


def test_count_figures_ignores_years():
    text = "60,921 rows, 22 309 CVE, 15616 train rows, season 2025, version 1.2"
    assert count_figures(text) == 3


def test_keyword_short_words_need_boundaries():
    assert count_keyword("we call the api twice", "api") == 1
    assert count_keyword("rapid capital", "api") == 0
    # long keywords match as prefixes (vulnerab -> vulnerability)
    assert count_keyword("vulnerability report", "vulnerab") == 1


def _profile(tmp_path, policy, files):
    repo_path = make_git_repo(tmp_path / "repo", files)
    meta = LocalCollector(tmp_path).build_metadata(
        LocalRepoEntry(full_name="me/repo", path=repo_path)
    )
    return RepoProfiler(policy).profile(
        meta, repo_path, has_tests=False, has_ci=False, now=datetime.now(UTC)
    )


def test_power_bi_project_is_detected_from_files(tmp_path, policy):
    profile = _profile(
        tmp_path,
        policy,
        {
            "README.md": "# Sales\nA Power BI report.",
            "report/Sales.SemanticModel/definition/tables/Sales.tmdl": "table Sales",
            "report/Sales.pbip": "{}",
        },
    )
    assert profile.primary_domain == "bi_reporting"
    assert any(e.endswith(".tmdl") for e in profile.domain_evidence["bi_reporting"])


def test_readme_keywords_alone_are_capped(tmp_path, policy):
    words = " ".join(["machine learning classification regression cross-validation"] * 30)
    profile = _profile(tmp_path, policy, {"README.md": words})
    cap = policy.domains["machine_learning"].keyword_cap
    assert profile.domain_strength["machine_learning"] <= cap + 1e-9


def test_imports_count_as_dependencies(tmp_path, policy):
    profile = _profile(
        tmp_path,
        policy,
        {"src/model.py": "from sklearn.linear_model import LogisticRegression\n" + "#" * 400},
    )
    assert "scikit-learn" in profile.dependencies


def test_tracked_personal_data_is_flagged(tmp_path, policy):
    profile = _profile(
        tmp_path,
        policy,
        {
            "data/students.csv": "nom;prenom;email;note\nDoe;John;j@x.fr;12\n",
            "data/kpis.csv": "month,revenue\n2024-01,10\n",
        },
    )
    assert profile.personal_data_files == ["data/students.csv"]


def test_theme_prefers_repo_name(tmp_path, policy):
    profile = _profile(tmp_path, policy, {"README.md": "Valorant VCT stats from VLR."})
    assert profile.theme == "esports"
