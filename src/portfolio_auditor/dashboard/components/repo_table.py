from __future__ import annotations

import streamlit as st

from portfolio_auditor.dashboard.data_loader import DashboardData


def render_repo_table(data: DashboardData, selected_repo: str) -> str:
    st.markdown("## Repository table")
    st.caption("Filter the portfolio inventory, compare repository quality, and select what to inspect next.")

    df = data.repo_df.copy()

    filter_cols = st.columns(4, gap="medium")
    with filter_cols[0]:
        score_range = st.slider(
            "Score range",
            min_value=0.0,
            max_value=100.0,
            value=(0.0, 100.0),
            step=0.5,
        )
    with filter_cols[1]:
        decisions = sorted(df["decision_label"].dropna().unique().tolist())
        selected_decisions = st.multiselect("Decision", options=decisions, default=decisions)
    with filter_cols[2]:
        redundancy_statuses = sorted(df["redundancy_status"].dropna().unique().tolist())
        selected_redundancy = st.multiselect(
            "Redundancy status",
            options=redundancy_statuses,
            default=redundancy_statuses,
        )
    with filter_cols[3]:
        languages = sorted(df["primary_language"].dropna().unique().tolist())
        selected_languages = st.multiselect("Language", options=languages, default=languages)

    show_public_focus = st.checkbox(
        "Show only repositories that should stay visible or be improved publicly",
        value=False,
    )

    filtered_df = df[
        (df["global_score"] >= score_range[0])
        & (df["global_score"] <= score_range[1])
        & (df["decision_label"].isin(selected_decisions))
        & (df["redundancy_status"].isin(selected_redundancy))
        & (df["primary_language"].isin(selected_languages))
    ].copy()

    if show_public_focus:
        filtered_df = filtered_df[filtered_df["decision_group"].isin(["keep", "improve"])]

    filtered_df = filtered_df.sort_values(
        ["action_priority", "estimated_recoverable_points", "global_score"],
        ascending=[False, False, False],
    )

    st.markdown(f"**Visible repositories: {len(filtered_df)} / {len(df)}**")
    st.dataframe(
        filtered_df[
            [
                "rank",
                "repo_name",
                "global_score",
                "score_label",
                "decision_label",
                "redundancy_status",
                "overlap_cluster_id",
                "primary_language",
                "priority_actions_count",
                "blockers_count",
                "issues_count",
                "action_priority",
                "estimated_recoverable_points",
                "top_action_roi",
                "next_action",
            ]
        ],
        use_container_width=True,
        hide_index=True,
        column_config={
            "global_score": st.column_config.NumberColumn("score", format="%.2f"),
            "action_priority": st.column_config.NumberColumn("priority", format="%.2f"),
            "estimated_recoverable_points": st.column_config.NumberColumn("upside", format="%.2f"),
            "top_action_roi": st.column_config.NumberColumn("ROI", format="%.2f"),
            "priority_actions_count": st.column_config.NumberColumn("priority_actions"),
            "overlap_cluster_id": st.column_config.TextColumn("cluster_id"),
            "primary_language": st.column_config.TextColumn("language"),
        },
    )

    selector_cols = st.columns([1.2, 1.8], gap="large")
    with selector_cols[0]:
        repo_options = filtered_df["repo_name"].tolist() or df["repo_name"].tolist()
        selected_repo = st.selectbox(
            "Inspect repository details",
            options=repo_options,
            index=repo_options.index(selected_repo) if selected_repo in repo_options else 0,
        )
    with selector_cols[1]:
        selected_row = df[df["repo_name"] == selected_repo].iloc[0]
        st.markdown(
            f"""
<div class="metric-card">
    <div class="card-title">Selected repository</div>
    <div class="card-value">#{int(selected_row['rank'])} · {selected_row['repo_full_name']}</div>
    <div class="card-caption">{selected_row['global_score']:.2f}/100 · {selected_row['decision_label']}</div>
    <div class="card-body">Next action: {selected_row['next_action']}</div>
    <div class="card-body">Recoverable score estimate: {selected_row['estimated_recoverable_points']:.2f} points · ROI {selected_row['top_action_roi']:.2f}</div>
</div>
""",
            unsafe_allow_html=True,
        )

    return selected_repo
