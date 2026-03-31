from __future__ import annotations

import os
from datetime import datetime, timezone

import requests
import streamlit as st

from portfolio_auditor.dashboard.components.optimizer_view import render_optimizer_view
from portfolio_auditor.dashboard.components.overview import render_overview
from portfolio_auditor.dashboard.components.portfolio_view import render_portfolio_view
from portfolio_auditor.dashboard.components.redundancy_view import render_redundancy_view
from portfolio_auditor.dashboard.components.repo_detail import render_repo_detail
from portfolio_auditor.dashboard.components.repo_table import render_repo_table
from portfolio_auditor.dashboard.data_loader import (
    DashboardDataError,
    discover_owners,
    load_dashboard_data,
)
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


def _resolve_default_owner() -> str | None:
    """
    Return the default owner from (in priority order):
    1. GITHUB_OWNER secret in Streamlit secrets
    2. GITHUB_OWNER environment variable
    3. settings.github_owner
    """
    try:
        secret_owner = st.secrets.get("GITHUB_OWNER")  # type: ignore[arg-type]
        if secret_owner and str(secret_owner).strip():
            return str(secret_owner).strip()
    except Exception:
        pass

    env_owner = os.getenv("GITHUB_OWNER", "").strip()
    if env_owner:
        return env_owner

    settings = get_settings()
    if settings.github_owner and settings.github_owner.strip():
        return settings.github_owner.strip()

    return None


def _render_staleness_indicator(base_dir_mtime: float | None) -> None:
    """
    Show a warning in the sidebar when cached artifacts are older than 24 h.
    """
    if base_dir_mtime is None:
        return

    age_seconds = (datetime.now(timezone.utc).timestamp() - base_dir_mtime)
    age_hours = age_seconds / 3600

    if age_hours < 1:
        age_label = "< 1 hour ago"
        color = "green"
    elif age_hours < 24:
        age_label = f"{int(age_hours)}h ago"
        color = "orange"
    else:
        age_label = f"{int(age_hours // 24)}d {int(age_hours % 24)}h ago"
        color = "red"

    st.markdown(
        f"<small>Last audit: <span style='color:{color};font-weight:600'>{age_label}</span></small>",
        unsafe_allow_html=True,
    )
    if age_hours >= 24:
        st.warning("Artifacts are more than 24 h old. Run a fresh audit to pick up new repositories.", icon="⚠️")


def _fetch_github_repo_names(owner: str) -> set[str]:
    """
    Lightweight GitHub fetch: only repository names.
    """
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}

    if token:
        headers["Authorization"] = f"Bearer {token}"
        url = "https://api.github.com/user/repos"
        params = {"per_page": 100, "visibility": "all"}
    else:
        url = f"https://api.github.com/users/{owner}/repos"
        params = {"per_page": 100}

    repo_names = set()
    page = 1

    while True:
        params["page"] = page
        resp = requests.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            break

        data = resp.json()
        if not data:
            break

        repo_names.update(repo["name"] for repo in data)
        page += 1

    return repo_names


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
        "Portfolio decision dashboard with live refresh. It can load existing processed "
        "artifacts or re-run the deterministic GitHub audit directly from Streamlit."
    )

    owners = discover_owners()
    default_owner = _resolve_default_owner()

    # Build owner options: always include the resolved default so the sidebar
    # is not empty on a fresh Streamlit Cloud deploy (no processed/ on disk yet).
    if owners:
        owner_options = owners
        if default_owner and default_owner not in owner_options:
            owner_options = [default_owner] + owner_options
    else:
        owner_options = [default_owner] if default_owner else ["MatALass"]

    # Pre-select the default owner when possible.
    default_index = 0
    if default_owner and default_owner in owner_options:
        default_index = owner_options.index(default_owner)

    with st.sidebar:
        st.header("Configuration")
        owner = st.selectbox("Owner", options=owner_options, index=default_index)
        refresh_clones = st.toggle("Refresh local clones during audit", value=True)
        st.caption(
            "Use refresh when repositories changed recently or when you want the latest "
            "local scan evidence."
        )
        if st.button("Run fresh audit now", type="primary", use_container_width=True):
            with st.spinner(
                "Refreshing portfolio artifacts from GitHub. This can take a while for "
                "larger portfolios."
            ):
                result = run_live_audit(owner, refresh_clones=refresh_clones)
            st.success(
                f"Audit finished. {result.analyzed_repo_count} repositories analyzed "
                f"for {result.owner}."
            )
            st.rerun()
        st.markdown("---")

    try:
        data = load_dashboard_data(owner)
        # --- Detect new repositories (lightweight GitHub sync)
        try:
            live_repo_names = _fetch_github_repo_names(owner)
            cached_repo_names = set(data.repo_df["repo_name"].tolist())

            new_repos = live_repo_names - cached_repo_names

        except Exception:
            new_repos = set()
    except DashboardDataError as exc:
        st.error(str(exc))
        st.info(
            "Run a fresh audit from the sidebar to generate the processed artifacts "
            "required by the dashboard."
        )
        st.stop()

    # Staleness indicator — use mtime of ranking.json as the audit timestamp proxy.
    ranking_path = data.base_dir / "ranking.json"
    mtime = ranking_path.stat().st_mtime if ranking_path.exists() else None
    with st.sidebar:
        _render_staleness_indicator(mtime)
        if new_repos:
            st.markdown("---")
            st.warning(
                f"{len(new_repos)} new repositories detected on GitHub.",
                icon="🆕",
            )

            with st.expander("Show new repositories"):
                for repo in sorted(new_repos):
                    st.write(f"- {repo}")

            if st.button("Refresh audit to include new repositories"):
                with st.spinner("Running audit for new repositories..."):
                    result = run_live_audit(owner, refresh_clones=refresh_clones)
                st.success(
                    f"Audit updated. {result.analyzed_repo_count} repositories analyzed."
                )
                st.rerun()
    repo_options = data.repo_df["repo_name"].tolist()
    with st.sidebar:
        selected_repo = st.selectbox("Repository detail", options=repo_options)
        st.markdown("---")
        st.markdown("### Current snapshot")
        st.metric(
            "Visible portfolio quality",
            f"{data.overview_metrics['portfolio_quality_score']:.2f}/100",
        )
        st.metric("Repositories analyzed", data.overview_metrics["total_repositories"])
        st.metric("Highlight now", data.overview_metrics["highlight_count"])
        st.metric(
            "After top 3 actions",
            f"{data.optimizer_summary['quality_after_top_3']:.2f}/100",
            delta=round(
                data.optimizer_summary["quality_after_top_3"]
                - data.optimizer_summary["current_quality"],
                2,
            ),
        )

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
                st.caption(
                    f"Compared with snapshot: "
                    f"{data.comparison_summary['snapshot_created_at_utc']}"
                )

        if data.next_actions:
            best_action = data.next_actions[0]
            st.markdown("---")
            st.markdown("### Best next move")
            st.write(best_action["action"])
            st.caption(
                f"Affects {best_action['affected_repo_count']} repos · Lift "
                f"{best_action['estimated_total_score_lift']:.2f} · "
                f"ROI {best_action['roi']:.2f}"
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