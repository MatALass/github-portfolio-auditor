from __future__ import annotations

import streamlit as st

from portfolio_auditor.dashboard.data_loader import DashboardData, _selection_repo_full_names


SECTION_CONFIG = [
    ("Highlight now", ["featured_repos"], "This is the public shortlist that is ready to represent the portfolio."),
    (
        "Keep visible but improve",
        ["keep_visible_but_improve"],
        "These repositories already create value, but they still need targeted engineering cleanup.",
    ),
    (
        "Improve / reposition",
        ["improvement_backlog", "redundancy_candidates"],
        "These repositories may become useful later, but they are not the strongest public signal yet.",
    ),
    (
        "Discard from public portfolio",
        ["archive_candidates", "private_candidates"],
        "These repositories should not stay in the public spotlight in their current state.",
    ),
]


def _render_repo_card(data: DashboardData, repo_full_name: str) -> None:
    repo_name = repo_full_name.split("/")[-1]
    row = data.repo_df[data.repo_df["repo_name"] == repo_name].iloc[0]
    review = data.review_index.get(repo_name, {})

    rationale = review.get("portfolio_rationale") or "No rationale available in artifacts."
    actions = review.get("priority_actions", []) or []
    quick_wins = review.get("quick_wins", []) or []
    top_action = row.get("next_action", "Review repository findings")

    st.markdown(
        f"""
<div class="repo-card">
    <div class="repo-card-header">
        <span class="repo-card-title">#{int(row['rank'])} · {repo_full_name}</span>
        <span class="repo-card-badge">{row['global_score']:.2f}/100 · {row['score_label'].upper()}</span>
    </div>
    <div class="repo-card-subtitle">{row['decision_label']} · {row['primary_language']} · Recoverable upside {row['estimated_recoverable_points']:.2f}</div>
    <div class="repo-card-body">{rationale}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    fact_cols = st.columns(3, gap="medium")
    fact_cols[0].metric("Next action", top_action)
    fact_cols[1].metric("Estimated upside", f"{row['estimated_recoverable_points']:.2f}")
    fact_cols[2].metric("Score ceiling", f"{row['score_ceiling']:.2f}/100")

    if actions:
        st.markdown("**Priority actions**")
        for action in actions[:3]:
            st.write(f"- {action.get('text', '')}")
    if quick_wins:
        st.markdown("**Quick wins**")
        for quick_win in quick_wins[:2]:
            st.write(f"- {quick_win.get('text', '')}")


def render_portfolio_view(data: DashboardData) -> None:
    st.markdown("## Portfolio selection")
    st.caption("The dashboard keeps the existing portfolio decision artifacts and reorganizes them into a clearer action view.")
    st.info(data.overview_metrics["manager_summary"])

    selection = data.portfolio_selection

    for title, keys, description in SECTION_CONFIG:
        repos = _selection_repo_full_names(selection, *keys)

        st.markdown(f"### {title} ({len(repos)})")
        st.caption(description)

        if not repos:
            st.success("No repositories in this section.")
            continue

        for repo_full_name in repos:
            expanded = title in {"Highlight now", "Keep visible but improve"}
            with st.expander(repo_full_name, expanded=expanded):
                _render_repo_card(data, repo_full_name)
