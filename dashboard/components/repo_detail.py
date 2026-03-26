from __future__ import annotations

import pandas as pd
import streamlit as st

from portfolio_auditor.dashboard.data_loader import DashboardData


def _items_to_bullet_list(items: list[dict], empty_label: str) -> str:
    if not items:
        return empty_label
    return "\n".join(f"- {item.get('text', '')}" for item in items)


def render_repo_detail(data: DashboardData, selected_repo: str) -> None:
    st.markdown("## Repository detail")
    row = data.repo_df[data.repo_df["repo_name"] == selected_repo].iloc[0]
    review = data.review_index.get(selected_repo, {})
    score_entry = data.score_index.get(selected_repo, {})
    scan_entry = data.scan_index.get(selected_repo, {})
    opportunities = row.get("optimizer_payload", []) or []

    st.markdown(f"### {row['repo_full_name']} · {row['global_score']:.2f}/100")
    if row.get("description"):
        st.caption(str(row["description"]))

    stat_cols = st.columns(5, gap="medium")
    stat_cols[0].metric("Rank", int(row["rank"]))
    stat_cols[1].metric("Decision", row["decision_label"])
    stat_cols[2].metric("Language", row["primary_language"])
    stat_cols[3].metric("Stars", int(row["stars"]))
    stat_cols[4].metric("Forks", int(row["forks"]))

    st.markdown("### Recommendation")
    st.info(review.get("portfolio_rationale") or "No portfolio rationale available.")

    optimizer_cols = st.columns(4, gap="medium")
    optimizer_cols[0].metric("Current score", f"{row['global_score']:.2f}/100")
    optimizer_cols[1].metric("Score ceiling", f"{row['score_ceiling']:.2f}/100", delta=round(row['score_ceiling'] - row['global_score'], 2))
    optimizer_cols[2].metric("Top action ROI", f"{row['top_action_roi']:.2f}")
    optimizer_cols[3].metric("Recoverable points", f"{row['estimated_recoverable_points']:.2f}")

    left, right = st.columns([1.05, 0.95], gap="large")

    with left:
        st.markdown("### Score breakdown")
        breakdown = score_entry.get("breakdown", {}) or {}
        breakdown_df = (
            pd.DataFrame(
                [{"category": key, "score": value} for key, value in breakdown.items()]
            )
            if breakdown
            else pd.DataFrame(columns=["category", "score"])
        )
        if not breakdown_df.empty:
            st.dataframe(
                breakdown_df,
                use_container_width=True,
                hide_index=True,
                column_config={"score": st.column_config.NumberColumn(format="%.2f")},
            )
        else:
            st.warning("No score breakdown available for this repository.")

        explanations = score_entry.get("explanations", []) or []
        if explanations:
            st.markdown("### Scoring explanations")
            for item in explanations:
                with st.expander(item.get("category", "category")):
                    st.write(item.get("summary", ""))
                    for point in item.get("supporting_points", []) or []:
                        st.write(f"- {point}")

        penalties = score_entry.get("penalties", []) or []
        if penalties:
            st.markdown("### Penalties limiting the score")
            penalties_df = pd.DataFrame(penalties)
            st.dataframe(penalties_df, use_container_width=True, hide_index=True)

    with right:
        st.markdown("### Review summary")
        st.markdown(review.get("executive_summary") or "No review summary available.")

        review_tabs = st.tabs(["Priority actions", "Quick wins", "Blockers", "Strengths", "Weaknesses"])
        review_tabs[0].markdown(_items_to_bullet_list(review.get("priority_actions", []) or [], "No priority action available."))
        review_tabs[1].markdown(_items_to_bullet_list(review.get("quick_wins", []) or [], "No quick win available."))
        review_tabs[2].markdown(_items_to_bullet_list(review.get("blockers", []) or [], "No blocker detected."))
        review_tabs[3].markdown(_items_to_bullet_list(review.get("strengths", []) or [], "No strength captured."))
        review_tabs[4].markdown(_items_to_bullet_list(review.get("weaknesses", []) or [], "No weakness captured."))

        st.markdown("### Improvement simulator")
        if opportunities:
            sim_df = pd.DataFrame(opportunities)[
                [
                    "text",
                    "estimated_score_lift",
                    "projected_score",
                    "effort_units",
                    "roi",
                    "matched_penalty_codes",
                ]
            ]
            st.dataframe(
                sim_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "estimated_score_lift": st.column_config.NumberColumn("lift", format="%.2f"),
                    "projected_score": st.column_config.NumberColumn("projected_score", format="%.2f"),
                    "effort_units": st.column_config.NumberColumn("effort", format="%.2f"),
                    "roi": st.column_config.NumberColumn("ROI", format="%.2f"),
                },
            )
        else:
            st.info("No deterministic improvement opportunities could be estimated for this repository.")

    st.markdown("### Detected issues")
    issues = scan_entry.get("issues", []) or []
    if issues:
        issues_df = pd.DataFrame(issues)
        preferred_columns = [column for column in ["severity", "code", "title", "recommendation"] if column in issues_df.columns]
        st.dataframe(issues_df[preferred_columns], use_container_width=True, hide_index=True)
    else:
        st.success("No issues recorded in repo_scans.json for this repository.")

    st.markdown("### Metadata and evidence")
    meta_left, meta_right = st.columns(2, gap="large")
    with meta_left:
        metadata_df = pd.DataFrame(
            [
                {"field": "HTML URL", "value": row.get("html_url")},
                {"field": "Homepage", "value": row.get("homepage") or "-"},
                {"field": "Confidence", "value": row.get("confidence")},
                {"field": "Redundancy status", "value": row.get("redundancy_status")},
                {"field": "Cluster ID", "value": row.get("overlap_cluster_id")},
            ]
        )
        st.dataframe(metadata_df, use_container_width=True, hide_index=True)
    with meta_right:
        evidence = scan_entry.get("evidence", []) or []
        if evidence:
            evidence_df = pd.DataFrame(evidence)
            preferred_columns = [column for column in ["source", "message", "path"] if column in evidence_df.columns]
            st.dataframe(evidence_df[preferred_columns], use_container_width=True, hide_index=True)
        else:
            st.info("No evidence rows available for this repository.")
