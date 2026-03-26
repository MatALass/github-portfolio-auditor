from __future__ import annotations

import pandas as pd
import streamlit as st

from portfolio_auditor.dashboard.data_loader import DashboardData


def render_optimizer_view(data: DashboardData) -> None:
    st.markdown("## Portfolio optimizer")
    st.caption(
        "This view converts existing penalties and priority actions into deterministic impact estimates. No rescoring is recomputed from source code."
    )

    optimizer = data.optimizer_summary
    top_actions = data.next_actions

    headline = st.columns(4, gap="medium")
    headline[0].metric("Visible quality now", f"{optimizer['current_quality']:.2f}/100")
    headline[1].metric(
        "After top action",
        f"{optimizer['quality_after_top_1']:.2f}/100",
        delta=round(optimizer['quality_after_top_1'] - optimizer['current_quality'], 2),
    )
    headline[2].metric(
        "After top 3 actions",
        f"{optimizer['quality_after_top_3']:.2f}/100",
        delta=round(optimizer['quality_after_top_3'] - optimizer['current_quality'], 2),
    )
    headline[3].metric(
        "Selected scope after top 3",
        f"{optimizer['selected_scope_after_top_3']:.2f}/100",
        delta=round(optimizer['selected_scope_after_top_3'] - optimizer['selected_scope_current'], 2),
    )

    left, right = st.columns([1.15, 0.85], gap="large")
    with left:
        st.markdown("### Action ranking by impact / effort")
        if top_actions:
            action_df = pd.DataFrame(top_actions)[
                [
                    "action",
                    "affected_repo_count",
                    "estimated_total_score_lift",
                    "total_effort_units",
                    "roi",
                ]
            ]
            st.dataframe(
                action_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "estimated_total_score_lift": st.column_config.NumberColumn("estimated_lift", format="%.2f"),
                    "total_effort_units": st.column_config.NumberColumn("effort", format="%.2f"),
                    "roi": st.column_config.NumberColumn("ROI", format="%.2f"),
                },
            )
        else:
            st.info("No portfolio action data is available.")
    with right:
        st.markdown("### How to read this")
        st.markdown(
            """
- **Estimated lift** = recoverable points already visible in penalty artifacts.
- **Effort** = deterministic relative effort, not a time estimate.
- **ROI** = estimated lift divided by effort.
- The best V2 move is not necessarily the highest-lift action; it is the best lift for the public scope with acceptable effort.
"""
        )

    st.markdown("### Top actions with repository targets")
    for idx, action in enumerate(top_actions[:6], start=1):
        with st.expander(f"#{idx} · {action['action']} · ROI {action['roi']:.2f}", expanded=(idx <= 2)):
            cols = st.columns(4, gap="medium")
            cols[0].metric("Affected repos", action["affected_repo_count"])
            cols[1].metric("Estimated lift", f"{action['estimated_total_score_lift']:.2f}")
            cols[2].metric("Effort", f"{action['total_effort_units']:.2f}")
            cols[3].metric("ROI", f"{action['roi']:.2f}")
            st.dataframe(
                pd.DataFrame(action["repos"]),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "global_score": st.column_config.NumberColumn("score", format="%.2f"),
                    "estimated_score_lift": st.column_config.NumberColumn("repo_lift", format="%.2f"),
                    "effort_units": st.column_config.NumberColumn("effort", format="%.2f"),
                    "roi": st.column_config.NumberColumn("ROI", format="%.2f"),
                },
            )

    st.markdown("### Highest-upside repositories")
    upside_df = data.repo_df[
        [
            "rank",
            "repo_name",
            "decision_label",
            "global_score",
            "estimated_recoverable_points",
            "score_ceiling",
            "top_action_roi",
            "next_action",
        ]
    ].sort_values(
        ["estimated_recoverable_points", "top_action_roi", "global_score"],
        ascending=[False, False, False],
    )
    st.dataframe(
        upside_df.head(12),
        use_container_width=True,
        hide_index=True,
        column_config={
            "global_score": st.column_config.NumberColumn("score", format="%.2f"),
            "estimated_recoverable_points": st.column_config.NumberColumn("recoverable", format="%.2f"),
            "score_ceiling": st.column_config.NumberColumn("ceiling", format="%.2f"),
            "top_action_roi": st.column_config.NumberColumn("ROI", format="%.2f"),
        },
    )
