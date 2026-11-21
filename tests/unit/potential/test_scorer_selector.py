from __future__ import annotations

import pytest

from portfolio_auditor.potential.policy import RepoOverride
from portfolio_auditor.potential.profiler import RepoProfile
from portfolio_auditor.potential.prompts import ImprovementPromptBuilder
from portfolio_auditor.potential.scorer import PotentialScorer
from portfolio_auditor.potential.selector import DiverseSelector, cosine

pytestmark = pytest.mark.unit


def profile(name: str, domains: dict[str, float], theme: str = "other", **kw) -> RepoProfile:
    base = dict(
        full_name=f"me/{name}",
        name=name,
        private=False,
        code_kb=120.0,
        notebook_count=0,
        python_module_count=8,
        readme_words=800,
        has_readme=True,
        has_visuals=True,
        has_demo_link=False,
        has_case_study=False,
        has_tests=True,
        has_ci=True,
        has_package_layout=True,
        tracked_kb=500,
        days_since_commit=10,
        commit_count=20,
        owner_commit_share=1.0,
        dependencies=[],
        domain_strength=domains,
        domain_evidence={},
        theme=theme,
        theme_hits={},
        realness_raw=2.0,
    )
    base.update(kw)
    return RepoProfile(**base)


def test_missing_pieces_lower_feasibility(policy):
    scorer = PotentialScorer(policy)
    ready = scorer.score(profile("a", {"sql_warehouse": 1.0}), 70)
    rough = scorer.score(
        profile("b", {"sql_warehouse": 1.0}, has_tests=False, has_ci=False, has_visuals=False),
        70,
    )
    assert ready.components["feasibility"] > rough.components["feasibility"]
    assert {"pas de tests", "pas de CI"} <= set(rough.effort_items)
    assert ready.potential > rough.potential


def test_personal_data_and_extra_effort_are_counted(policy):
    scorer = PotentialScorer(policy)
    p = profile("a", {"data_pipeline": 1.0}, personal_data_files=["data/x.csv"])
    s = scorer.score(p, 60, RepoOverride(extra_effort={"anonymiser": 2}))
    assert "données personnelles versionnées" in s.effort_items
    assert "anonymiser" in s.effort_items


def test_override_excludes_and_corrects(policy):
    scorer = PotentialScorer(policy)
    p = profile("a", {"web_frontend": 0.9, "decision_simulation": 0.7})
    s = scorer.score(p, 80, RepoOverride(primary_domain="decision_simulation", theme="cards"))
    assert s.primary_domain == "decision_simulation"
    assert s.theme == "cards"
    excluded = scorer.score(p, 80, RepoOverride(exclude="site perso"))
    assert not excluded.eligible and excluded.exclusion_reason == "site perso"


def test_other_peoples_work_is_not_eligible(policy):
    s = PotentialScorer(policy).score(
        profile("a", {"machine_learning": 1.0}, owner_commit_share=0.1), 70
    )
    assert not s.eligible


def test_cosine_basic():
    assert cosine({"a": 1}, {"a": 2}) == pytest.approx(1.0)
    assert cosine({"a": 1}, {"b": 1}) == 0.0
    assert cosine({}, {"a": 1}) == 0.0


def _run_selection(policy, profiles):
    scorer = PotentialScorer(policy)
    scores = sorted(
        (scorer.score(p, 75) for p in profiles), key=lambda s: s.potential, reverse=True
    )
    return DiverseSelector(policy).select(scores, {p.full_name: p for p in profiles})


def test_selector_caps_one_repo_per_theme(policy):
    profiles = [
        profile("vct1", {"bi_reporting": 1.0}, theme="esports"),
        profile("vct2", {"data_pipeline": 1.0}, theme="esports"),
        profile("sql", {"sql_warehouse": 1.0}, theme="education"),
    ]
    result = _run_selection(policy, profiles)
    chosen = result.featured + result.bench
    assert sum(name in chosen for name in ("me/vct1", "me/vct2")) == 1
    assert "me/sql" in chosen
    assert any("esports" in reason for reason in result.skipped_for_diversity.values())


def test_selector_never_features_off_role_domains(policy):
    profiles = [
        profile("game", {"game_dev": 1.0, "data_app": 0.6}, theme="video_games"),
        profile("bi", {"bi_reporting": 1.0}, theme="sales"),
    ]
    result = _run_selection(policy, profiles)
    assert "me/game" not in result.featured + result.bench


def test_selector_prefers_new_skills(policy):
    profiles = [
        profile("bi1", {"bi_reporting": 1.0}, theme="t1"),
        profile("bi2", {"bi_reporting": 1.0}, theme="t2"),
        profile("sql", {"sql_warehouse": 1.0}, theme="t3", realness_raw=1.0),
    ]
    policy.selection.featured_count = 2
    policy.selection.bench_count = 0
    result = _run_selection(policy, profiles)
    assert "me/sql" in result.featured


def test_prompt_mentions_role_facts_and_privacy(policy):
    p = profile("a", {"sql_warehouse": 1.0}, private=True, has_tests=False)
    s = PotentialScorer(policy).score(p, 55)
    text = ImprovementPromptBuilder(policy).build(
        s, p, portfolio_role="projet mis en avant n°1 sur 6", siblings=["b", "c"]
    )
    assert "SQL et entrepôt de données" in text
    assert "pytest" in text  # fix for missing tests
    assert "privé" in text
    assert "b, c" in text
    assert "—" not in text  # no em dash in generated prompts
