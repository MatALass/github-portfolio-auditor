from __future__ import annotations

import streamlit as st

DASHBOARD_STYLES = """
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
"""


def inject_styles() -> None:
    st.markdown(DASHBOARD_STYLES, unsafe_allow_html=True)
