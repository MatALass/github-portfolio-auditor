from __future__ import annotations

import pandas as pd
import streamlit as st

from portfolio_auditor.dashboard.data_loader import DashboardData


def render_redundancy_view(data: DashboardData) -> None:
    st.markdown("## Redundancy analysis")
    st.caption("Cluster-level redundancy is read directly from redundancy_analysis.json. The dashboard does not recompute overlap.")

    redundancy = data.redundancy_analysis
    clusters = redundancy.get("overlap_clusters", []) or []
    pairs = redundancy.get("overlap_pairs", []) or []

    status_distribution = (
        data.repo_df["redundancy_status"]
        .value_counts()
        .rename_axis("redundancy_status")
        .reset_index(name="repo_count")
    )

    if not clusters:
        st.success("No redundancy clusters were detected in the processed artifacts.")
        left, right = st.columns([1.0, 1.2], gap="large")
        with left:
            st.markdown("### Status distribution")
            st.dataframe(status_distribution, use_container_width=True, hide_index=True)
        with right:
            st.markdown("### What this means")
            st.markdown(
                """
- No overlap cluster crossed the configured threshold.
- The current portfolio problem is therefore not duplication, but quality concentration.
- The next optimization step is to improve the public shortlist rather than merge repositories.
"""
            )
            if pairs:
                st.markdown("### Near-overlap evidence")
                st.dataframe(pd.DataFrame(pairs).head(10), use_container_width=True, hide_index=True)
        return

    st.markdown("### Overlap clusters")
    for cluster in clusters:
        cluster_id = cluster.get("cluster_id", "unknown")
        representative = cluster.get("representative_repo_full_name", "Unknown")
        members = cluster.get("repos", []) or []
        with st.expander(f"Cluster {cluster_id} · representative: {representative}"):
            st.write(f"Repositories in cluster: {len(members)}")
            st.dataframe(pd.DataFrame(members), use_container_width=True, hide_index=True)

    if pairs:
        st.markdown("### Pair-level overlap evidence")
        st.dataframe(pd.DataFrame(pairs), use_container_width=True, hide_index=True)
