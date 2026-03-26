from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from portfolio_auditor.dashboard.components.optimizer_view import render_optimizer_view
from portfolio_auditor.dashboard.components.overview import render_overview
from portfolio_auditor.dashboard.components.portfolio_view import render_portfolio_view
from portfolio_auditor.dashboard.components.redundancy_view import render_redundancy_view
from portfolio_auditor.dashboard.components.repo_detail import render_repo_detail
from portfolio_auditor.dashboard.components.repo_table import render_repo_table
from portfolio_auditor.dashboard.data_loader import DashboardDataError, discover_owners, load_dashboard_data
from portfolio_auditor.dashboard.live_audit import ensure_streamlit_secrets_in_env, run_live_audit
from portfolio_auditor.settings import get_settings, reset_settings_cache


def _inject_styles() -> None:
    st.markdown(
        """
<style>
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2rem;
        max-width: 1540px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }
    .stTabs [data-baseweb="tab"] {
        height: 3rem;
        padding: 0 1rem;
        font-size: 0.98rem;
        font-weight: 600;
    }
    h1, h2, h3 {
        letter-spacing: -0.02em;
    }
    .metric-card, .repo-card {
        border: 1px solid rgba(49, 51, 63, 0.12);
        border-radius: 16px;
        padding: 1rem 1.1rem;
        background: rgba(255, 255, 255, 0.02);
        margin-bottom: 0.8rem;
    }
    .card-title {
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #6b7280;
        margin-bottom: 0.35rem;
        font-weight: 700;
    }
    .card-value {
        font-size: 1.25rem;
        font-weight: 700;
        line-height: 1.35;
        color: #111827;
        margin-bottom: 0.25rem;
    }
    .card-caption {
        font-size: 0.92rem;
        color: #4b5563;
        margin-bottom: 0.4rem;
    }
    .card-body {
        font-size: 0.98rem;
        line-height: 1.5;
        color: #111827;
    }
</style>
""",
        unsafe_allow_html=True,
    )


def _configure_runtime_environment() -> None:
    ensure_streamlit_secrets_in_env()
    try:
        excluded = st.secrets.get("GITHUB_EXCLUDED_REPO_NAMES")  # type: ignore[arg-type]
    except Exception:
        excluded = None
    if excluded and not os.getenv("GITHUB_EXCLUDED_REPO_NAMES"):
        os.environ["GITHUB_EXCLUDED_REPO_NAMES"] = str(excluded)
    reset_settings_cache()
    get_settings()


def main() -> None:
    st.set_page_config(
        page_title="GitHub Portfolio Auditor Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_styles()
    _configure_runtime_environment()

    st.title("GitHub Portfolio Auditor · Dashboard V2.5")
    st.caption(
        "Portfolio decision dashboard with live refresh. It can load existing processed artifacts or re-run the deterministic GitHub audit directly from Streamlit."
    )

    owners = discover_owners()
    owner_options = owners if owners else ["MatALass"]

    with st.sidebar:
        st.header("Configuration")
        owner = st.selectbox("Owner", options=owner_options)
        refresh_clones = st.toggle("Refresh local clones during audit", value=True)
        st.caption("Use refresh when repositories changed recently or when you want the latest local scan evidence.")
        if st.button("Run fresh audit now", type="primary", use_container_width=True):
            with st.spinner("Refreshing portfolio artifacts from GitHub. This can take a while for larger portfolios."):
                result = run_live_audit(owner, refresh_clones=refresh_clones)
            st.success(f"Audit finished. {result.analyzed_repo_count} repositories analyzed for {result.owner}.")
            st.rerun()
        st.markdown("---")

    try:
        data = load_dashboard_data(owner)
    except DashboardDataError as exc:
        st.error(str(exc))
        st.info(
            "Run a fresh audit from the sidebar to generate the processed artifacts required by the dashboard."
        )
        st.stop()

    repo_options = data.repo_df["repo_name"].tolist()
    with st.sidebar:
        selected_repo = st.selectbox("Repository detail", options=repo_options)
        st.markdown("---")
        st.markdown("### Current snapshot")
        st.metric("Visible portfolio quality", f"{data.overview_metrics['portfolio_quality_score']:.2f}/100")
        st.metric("Repositories analyzed", data.overview_metrics["total_repositories"])
        st.metric("Highlight now", data.overview_metrics["highlight_count"])
        st.metric("After top 3 actions", f"{data.optimizer_summary['quality_after_top_3']:.2f}/100", delta=round(data.optimizer_summary['quality_after_top_3'] - data.optimizer_summary['current_quality'], 2))

        if data.comparison_summary:
            st.markdown("---")
            st.markdown("### Since previous refresh")
            st.metric("Improved repos", data.comparison_summary["improved_count"])
            st.metric("Declined repos", data.comparison_summary["declined_count"])
            st.metric(
                "Selected scope delta",
                f"{data.comparison_summary['current_selected_scope_avg']:.2f}/100",
                delta=data.comparison_summary["selected_scope_delta"],
            )
            if data.comparison_summary.get("snapshot_created_at_utc"):
                st.caption(f"Compared with snapshot: {data.comparison_summary['snapshot_created_at_utc']}")

        if data.next_actions:
            best_action = data.next_actions[0]
            st.markdown("---")
            st.markdown("### Best next move")
            st.write(best_action["action"])
            st.caption(
                f"Affects {best_action['affected_repo_count']} repos · Lift {best_action['estimated_total_score_lift']:.2f} · ROI {best_action['roi']:.2f}"
            )

    tabs = st.tabs(
        [
            "Overview",
            "Repository Table",
            "Portfolio Selection",
            "Redundancy",
            "Repository Detail",
            "Optimizer",
        ]
    )

    with tabs[0]:
        render_overview(data)

    with tabs[1]:
        selected_repo = render_repo_table(data, selected_repo)

    with tabs[2]:
        render_portfolio_view(data)

    with tabs[3]:
        render_redundancy_view(data)

    with tabs[4]:
        render_repo_detail(data, selected_repo)

    with tabs[5]:
        render_optimizer_view(data)


if __name__ == "__main__":
    main()
