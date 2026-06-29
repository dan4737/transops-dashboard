"""
app.py
======
Entry point for the TransOps Transportation Intelligence Dashboard.

Streamlit automatically turns the files in `pages/` into a multi-page app with
sidebar navigation. This file is the landing page: it introduces the tool,
shows a live high-level snapshot of the fleet, and points users to the detailed
pages.

Run locally with:

    streamlit run app.py
"""

import sys
import os

# Ensure project root is importable before we pull in utils.*
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import streamlit as st

from utils.ui import page_setup, BRAND, TAGLINE, COLORS
from utils import db

page_setup("Home", icon="🚚")

# Start the background scheduler once per server process (hourly anomaly
# refresh + daily/weekly report generation). Best-effort: never blocks the app.
try:
    from utils.scheduler import start_scheduler
    start_scheduler()
except Exception:
    pass

# --------------------------------------------------------------------------- #
# Load data (auto-generates the database on first run if missing)
# --------------------------------------------------------------------------- #
deliveries = db.load_deliveries()
vehicles = db.load_vehicles()
routes = db.load_routes()

# --------------------------------------------------------------------------- #
# Hero / intro
# --------------------------------------------------------------------------- #
st.title("🚚 TransOps — Transportation Intelligence Dashboard")
st.markdown(
    """
    A live operations cockpit for a regional Ontario carrier. It tracks delivery
    performance, fleet health, incidents, and automatically flags emerging
    problems — the kind of internal tool a logistics operations team relies on
    every morning.
    """
)
st.divider()

# --------------------------------------------------------------------------- #
# Live snapshot KPIs
# --------------------------------------------------------------------------- #
today = pd.Timestamp.now().normalize()
last7 = deliveries[deliveries["date"] >= today - pd.Timedelta(days=7)]
on_time_rate = 100 * deliveries["is_on_time"].mean()
on_time_7d = 100 * last7["is_on_time"].mean() if len(last7) else 0
active_vehicles = int((vehicles["current_status"] == "In Transit").sum())
overdue = int(vehicles["maintenance_overdue"].sum())

st.subheader("Fleet snapshot")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total deliveries (90d)", f"{len(deliveries):,}")
c2.metric("Overall on-time rate", f"{on_time_rate:.1f}%")
c3.metric("On-time (last 7d)", f"{on_time_7d:.1f}%")
c4.metric("Vehicles in transit", active_vehicles)
c5.metric("Maintenance overdue", overdue, delta=None,
          help="Vehicles not serviced in over 90 days")

if overdue > 0:
    st.warning(
        f"⚠️ {overdue} vehicle(s) are overdue for maintenance. "
        "See the **Vehicle Management** page."
    )

st.divider()

# --------------------------------------------------------------------------- #
# Navigation guide
# --------------------------------------------------------------------------- #
st.subheader("What's inside")
col_a, col_b = st.columns(2)
with col_a:
    st.markdown(
        """
        - **📊 Executive Overview** — weekly KPIs, delivery volume trends
        - **🗺️ Route Performance** — best/worst lanes, on-time by route
        - **🚛 Vehicle Management** — fleet status & maintenance flags
        """
    )
with col_b:
    st.markdown(
        """
        - **⚠️ Incident & Delay Analysis** — root causes & trends
        - **📄 Automated Reports** — one-click daily / weekly PDF reports
        - **🚨 Anomaly Alerts** — rule-based early-warning system
        """
    )

st.caption("Use the sidebar to navigate between pages. Every page has its own filters.")

# Footer
st.divider()
st.caption(
    f"{BRAND} · {TAGLINE} · Data simulated for portfolio demonstration · "
    f"Coverage: {deliveries['date'].min().date()} → {deliveries['date'].max().date()}"
)
