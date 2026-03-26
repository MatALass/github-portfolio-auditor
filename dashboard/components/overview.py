from __future__ import annotations

import pandas as pd
import streamlit as st

from portfolio_auditor.dashboard.data_loader import DashboardData


def _metric_card(title: str, value: str, caption: str = "") -> None:
    st.markdown(
        f"""
<div class="metric-card">
    <div class="card-title">{title}</div>
    <div class="card-value">{value}</div>
    <div class="card-caption">{caption}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _action_card(index: int, action: dict) -> None:
    examples = ", ".join(repo["repo_name"] for repo in action.get("repos", [])[:3])
    st.markdown(
        f"""
<div class="metric-card action-card">
    <div class="card-title">Action #{index}</div>
    <div class="card-value action-text">{action['action']}</div>
    <div class="card-caption">Affects {action['affected_repo_count']} repositories · Estimated lift {action['estimated_total_score_lift']:.2f} pts · ROI {action['roi']:.2f}</div>
    <div class="card-body">Examples: {examples or 'n/a'}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_overview(data: DashboardData) -> None:
    metrics = data.overview_metrics
    optimizer = data.optimizer_summary
    df = data.repo_df

    top = st.columns([1.9, 0.9], gap="large")
    with top[0]:
        st.markdown("## Portfolio decision overview")
        st.write(
            "Use this page to decide what to showcase now, what to improve next, and how the portfolio changed after the latest refresh."
        )
        st.info(metrics["manager_summary"])
    with top[1]:
        st.markdown("## Interpretation")
        _metric_card(
            "Visible portfolio quality",
            f"{metrics['portfolio_quality_score']:.2f}/100",
            f"Public-facing quality. Raw all-repository average remains {metrics['global_average_score']:.2f}/100.",
        )

    row_one = st.columns(4, gap="medium")
    with row_one[0]:
        _metric_card("Repositories analyzed", str(metrics["total_repositories"]), "Current audited inventory")
    with row_one[1]:
        _metric_card("Raw portfolio median", f"{metrics['median_score']:.2f}/100", "Median across all repositories, including weak archives.")
    with row_one[2]:
        _metric_card("Highlight now", str(metrics["highlight_count"]), "Repositories already strong enough to feature directly.")
    with row_one[3]:
        _metric_card("Redundancy clusters", str(metrics["redundancy_clusters"]), "Overlap clusters detected from redundancy analysis")

    row_two = st.columns(4, gap="medium")
    with row_two[0]:
        _metric_card("Keep visible", str(metrics["keep_visible_count"]), "Public repositories worth keeping while improving them.")
    with row_two[1]:
        _metric_card("Improve backlog", str(metrics["improvement_backlog_count"]), "Repos with upside but not strong enough to represent the portfolio yet.")
    with row_two[2]:
        _metric_card("Discard candidates", str(metrics["discard_count"]), "Repos that should leave the public spotlight in current state.")
    with row_two[3]:
        _metric_card("Selected scope avg", f"{metrics['selected_scope_average']:.2f}/100", "Average across keep + improve scope.")

    if data.comparison_summary and data.comparison_df is not None:
        st.markdown("### Since previous refresh")
        comp = data.comparison_summary
        comparison_cols = st.columns(5, gap="medium")
        comparison_cols[0].metric("Improved", comp["improved_count"])
        comparison_cols[1].metric("Declined", comp["declined_count"])
        comparison_cols[2].metric("New repos", comp["new_count"])
        comparison_cols[3].metric("Removed repos", comp["removed_count"])
        comparison_cols[4].metric(
            "Selected scope delta",
            f"{comp['current_selected_scope_avg']:.2f}/100",
            delta=comp["selected_scope_delta"],
        )
        st.caption(
            f"Comparison baseline: {comp.get('snapshot_created_at_utc') or comp['snapshot_label']}"
        )

        left, right = st.columns(2, gap="large")
        with left:
            st.markdown("#### Top improvements")
            improved = pd.DataFrame(comp.get("top_improvements", []))
            if not improved.empty:
                st.dataframe(
                    improved[["repo_name", "previous_score", "current_score", "score_delta", "previous_decision", "current_decision"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "previous_score": st.column_config.NumberColumn("prev", format="%.2f"),
                        "current_score": st.column_config.NumberColumn("current", format="%.2f"),
                        "score_delta": st.column_config.NumberColumn("delta", format="%.2f"),
                    },
                )
            else:
                st.info("No score improvements were detected against the previous refresh.")
        with right:
            st.markdown("#### Top declines")
            declined = pd.DataFrame(comp.get("top_declines", []))
            if not declined.empty:
                st.dataframe(
                    declined[["repo_name", "previous_score", "current_score", "score_delta", "previous_decision", "current_decision"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "previous_score": st.column_config.NumberColumn("prev", format="%.2f"),
                        "current_score": st.column_config.NumberColumn("current", format="%.2f"),
                        "score_delta": st.column_config.NumberColumn("delta", format="%.2f"),
                    },
                )
            else:
                st.success("No score declines were detected against the previous refresh.")

    st.markdown("### Score label distribution")
    left, right = st.columns([1.1, 0.9], gap="large")
    with left:
        score_distribution = (
            df["score_label"].value_counts().rename_axis("score_label").reset_index(name="repo_count")
        )
        st.bar_chart(score_distribution.set_index("score_label"))
    with right:
        decision_df = (
            df["decision_label"].value_counts().rename_axis("decision").reset_index(name="repo_count")
        )
        st.markdown("### Portfolio decision buckets")
        st.dataframe(decision_df, use_container_width=True, hide_index=True)

    st.markdown("### Portfolio improvement simulator")
    sim_cols = st.columns(4, gap="medium")
    sim_cols[0].metric("Current visible quality", f"{optimizer['current_quality']:.2f}/100")
    sim_cols[1].metric(
        "After top 1 action",
        f"{optimizer['quality_after_top_1']:.2f}/100",
        delta=round(optimizer['quality_after_top_1'] - optimizer['current_quality'], 2),
    )
    sim_cols[2].metric(
        "After top 3 actions",
        f"{optimizer['quality_after_top_3']:.2f}/100",
        delta=round(optimizer['quality_after_top_3'] - optimizer['current_quality'], 2),
    )
    sim_cols[3].metric(
        "Selected scope after top 3",
        f"{optimizer['selected_scope_after_top_3']:.2f}/100",
        delta=round(optimizer['selected_scope_after_top_3'] - optimizer['selected_scope_current'], 2),
    )
    st.caption(
        "Simulation is deterministic and based only on existing score penalties + priority actions. It estimates recoverable points; it does not re-run the auditor."
    )

    if optimizer["top_actions"]:
        st.markdown("### Highest-impact actions")
        action_cols = st.columns(min(3, len(optimizer["top_actions"])), gap="medium")
        for index, (column, action) in enumerate(zip(action_cols, optimizer["top_actions"], strict=False), start=1):
            with column:
                _action_card(index, action)
