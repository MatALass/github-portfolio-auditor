from __future__ import annotations

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


def _inject_styles() -> None:
    st.markdown(
        """
<style>
    .block-container {
        padding-top: 1.5rem;
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
    p, li, .stCaption {
        font-size: 1rem;
    }
    .metric-card, .repo-card {
        border: 1px solid rgba(49, 51, 63, 0.12);
        border-radius: 16px;
        padding: 1rem 1.1rem;
        background: rgba(255, 255, 255, 0.02);
        margin-bottom: 0.8rem;
    }
    .action-card {
        min-height: 158px;
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
    .action-text {
        font-size: 1.05rem;
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
    .repo-card-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 0.75rem;
        margin-bottom: 0.4rem;
    }
    .repo-card-title {
        font-weight: 700;
        font-size: 1.05rem;
        color: #111827;
    }
    .repo-card-badge {
        font-size: 0.84rem;
        font-weight: 700;
        background: rgba(59, 130, 246, 0.12);
        color: #1d4ed8;
        border-radius: 999px;
        padding: 0.32rem 0.7rem;
        white-space: nowrap;
    }
    .repo-card-subtitle {
        font-size: 0.92rem;
        color: #4b5563;
        margin-bottom: 0.5rem;
    }
    .repo-card-body {
        font-size: 0.98rem;
        line-height: 1.5;
        color: #111827;
    }
</style>
""",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="GitHub Portfolio Auditor Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_styles()

    st.title("GitHub Portfolio Auditor · Dashboard V2")
    st.caption(
        "Deterministic portfolio decision dashboard powered only by processed JSON artifacts. V2 adds impact simulation and optimization views without rescanning repositories."
    )

    owners = discover_owners()
    if not owners:
        st.error("No processed owner directory was found under data/processed. Run the CLI pipeline first.")
        st.stop()

    with st.sidebar:
        st.header("Configuration")
        owner = st.selectbox("Owner", options=owners)

    try:
        data = load_dashboard_data(owner)
    except DashboardDataError as exc:
        st.error(str(exc))
        st.stop()

    repo_options = data.repo_df["repo_name"].tolist()
    with st.sidebar:
        selected_repo = st.selectbox("Repository detail", options=repo_options)
        st.markdown("---")
        st.markdown("### Snapshot")
        st.metric("Portfolio quality now", f"{data.overview_metrics['portfolio_quality_score']:.2f}/100")
        st.metric("Repositories analyzed", data.overview_metrics["total_repositories"])
        st.metric("Discard candidates", data.overview_metrics["discard_count"])
        st.metric(
            "After top 3 actions",
            f"{data.optimizer_summary['quality_after_top_3']:.2f}/100",
            delta=round(
                data.optimizer_summary["quality_after_top_3"] - data.optimizer_summary["current_quality"],
                2,
            ),
        )
        if data.next_actions:
            best_action = data.next_actions[0]
            st.markdown("---")
            st.markdown("### Best next move")
            st.write(best_action["action"])
            st.caption(
                f"Affects {best_action['affected_repo_count']} repos · Lift {best_action['estimated_total_score_lift']:.2f} · ROI {best_action['roi']:.2f}"
            )
        st.caption("Use the optimizer tab to compare impact vs effort and decide the next portfolio upgrade batch.")

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
