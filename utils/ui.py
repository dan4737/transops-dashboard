"""
ui.py
=====
Shared UI helpers so all six pages share consistent branding, colour coding,
and sidebar filters. Keeping these in one place is what makes the app feel like
a single internal tool ("TransOps Dashboard") instead of six separate scripts.

Also handles a small but important detail: when a page is opened directly, the
project root may not be on the Python path, so `import utils.db` would fail.
Importing this module first fixes the path for every page.
"""

from __future__ import annotations

import os
import sys

# --- Make `utils.*` importable no matter how the page is launched ----------- #
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pandas as pd
import streamlit as st


# --------------------------------------------------------------------------- #
# Branding & colour system
# --------------------------------------------------------------------------- #

BRAND = "TransOps"
TAGLINE = "Transportation Intelligence Dashboard"

# Consistent status colours used across every chart and table on every page.
COLORS = {
    "On Time": "#2E7D32",     # green
    "Delayed": "#EF6C00",     # orange
    "Cancelled": "#9E9E9E",   # grey
    "Failed": "#C62828",      # red
    "good": "#2E7D32",
    "warning": "#F9A825",
    "bad": "#C62828",
    "accent": "#1565C0",
}

SEVERITY_COLORS = {"High": "#C62828", "Medium": "#EF6C00", "Low": "#F9A825"}


def page_setup(title: str, icon: str = "🚚") -> None:
    """
    Standard page configuration + sidebar branding. Call once at the top of
    every page, before any other Streamlit command.
    """
    st.set_page_config(
        page_title=f"{BRAND} | {title}",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    with st.sidebar:
        st.markdown(f"## 🚚 {BRAND}")
        st.caption(TAGLINE)
        st.divider()


def page_header(title: str, subtitle: str = "") -> None:
    """Consistent page title block in the main area."""
    st.title(title)
    if subtitle:
        st.caption(subtitle)


# --------------------------------------------------------------------------- #
# Sidebar filters (shared)
# --------------------------------------------------------------------------- #

def date_range_filter(df: pd.DataFrame, key: str, default_days: int = 30):
    """
    Render a sidebar date-range picker bounded by the data, defaulting to the
    most recent `default_days`. Returns (start_date, end_date) as Timestamps.
    """
    data_min = df["date"].min().date()
    data_max = df["date"].max().date()
    default_start = max(data_min, (df["date"].max() - pd.Timedelta(days=default_days)).date())

    st.sidebar.markdown("### 📅 Date range")
    picked = st.sidebar.date_input(
        "Select period",
        value=(default_start, data_max),
        min_value=data_min,
        max_value=data_max,
        key=f"date_{key}",
    )

    # date_input returns a single date until both ends are chosen.
    if isinstance(picked, tuple) and len(picked) == 2:
        start, end = picked
    else:
        start, end = default_start, data_max
    return pd.Timestamp(start), pd.Timestamp(end)


def multiselect_filter(label: str, options, key: str):
    """Generic sidebar multiselect; empty selection means 'all'."""
    chosen = st.sidebar.multiselect(label, sorted(options), default=[], key=key)
    return chosen if chosen else list(options)


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #

def pct(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}%"


def color_for_rate(rate: float, good: float = 90, warn: float = 75) -> str:
    """Return a status colour for an on-time-style percentage."""
    if rate >= good:
        return COLORS["good"]
    if rate >= warn:
        return COLORS["warning"]
    return COLORS["bad"]
