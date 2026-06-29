"""
01_overview.py — Executive Overview
===================================
The morning-briefing page. Answers "how are we doing right now?" at a glance:

  * This week vs last week delivery volume (delta metric)
  * Headline on-time delivery rate
  * Average delivery time across all routes
  * Incidents this week
  * Fleet utilisation
  * Daily delivery volume trend (line)
  * On-time / delayed / cancelled / failed by week (bar)

Top KPI cards compare the most recent 7 days against the previous 7 days, so
they always reflect "this week vs last week" regardless of the sidebar filter.
The two trend charts respect the sidebar date range for exploration.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.ui import page_setup, page_header, date_range_filter, COLORS
from utils import db

page_setup("Executive Overview", icon="📊")
page_header("📊 Executive Overview", "Week-over-week performance and 30-day trends")

# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
deliveries = db.load_deliveries()
vehicles = db.load_vehicles()

latest = deliveries["date"].max()

# Rolling weekly windows anchored to the most recent data.
this_week = deliveries[deliveries["date"] > latest - pd.Timedelta(days=7)]
last_week = deliveries[
    (deliveries["date"] <= latest - pd.Timedelta(days=7))
    & (deliveries["date"] > latest - pd.Timedelta(days=14))
]


def on_time_rate(df: pd.DataFrame) -> float:
    return 100 * df["is_on_time"].mean() if len(df) else 0.0


def avg_delivery_hours(df: pd.DataFrame) -> float:
    """Average actual transit time (hours) for completed trips."""
    done = df.dropna(subset=["actual_departure", "actual_arrival"])
    if not len(done):
        return 0.0
    hours = (done["actual_arrival"] - done["actual_departure"]).dt.total_seconds() / 3600
    return hours.mean()


# --------------------------------------------------------------------------- #
# KPI row — this week vs last week
# --------------------------------------------------------------------------- #
st.markdown("#### This week vs last week")
k1, k2, k3, k4, k5 = st.columns(5)

vol_now, vol_prev = len(this_week), len(last_week)
k1.metric(
    "Deliveries this week",
    f"{vol_now:,}",
    delta=f"{vol_now - vol_prev:+d} vs last week",
)

ot_now, ot_prev = on_time_rate(this_week), on_time_rate(last_week)
k2.metric(
    "On-time rate",
    f"{ot_now:.1f}%",
    delta=f"{ot_now - ot_prev:+.1f} pts",
)

avg_now = avg_delivery_hours(this_week)
avg_all = avg_delivery_hours(deliveries)
k3.metric(
    "Avg delivery time",
    f"{avg_now:.1f} h",
    delta=f"{avg_now - avg_all:+.1f} h vs 90d avg",
    delta_color="inverse",  # longer = worse
)

inc_now = int(this_week["incidents_reported"].sum())
inc_prev = int(last_week["incidents_reported"].sum())
k4.metric(
    "Incidents this week",
    inc_now,
    delta=f"{inc_now - inc_prev:+d} vs last week",
    delta_color="inverse",
)

# Fleet utilisation = share of the fleet that ran at least one trip this week.
active_vehicles = this_week["vehicle_id"].nunique()
utilisation = 100 * active_vehicles / len(vehicles) if len(vehicles) else 0
k5.metric(
    "Vehicle utilisation",
    f"{utilisation:.0f}%",
    help="Share of fleet that ran at least one delivery in the last 7 days",
)

st.divider()

# --------------------------------------------------------------------------- #
# Sidebar filter (drives the trend charts below)
# --------------------------------------------------------------------------- #
start, end = date_range_filter(deliveries, key="overview", default_days=30)
window = db.filter_by_date(deliveries, start, end)
st.caption(f"Charts below cover **{start.date()} → {end.date()}** "
           f"({len(window):,} deliveries).")

# --------------------------------------------------------------------------- #
# Daily delivery volume (line)
# --------------------------------------------------------------------------- #
st.subheader("Daily delivery volume")
daily = (
    window.groupby(window["date"].dt.date)
    .size()
    .reset_index(name="deliveries")
    .rename(columns={"date": "Date"})
)
if len(daily):
    fig_line = px.line(
        daily, x="Date", y="deliveries", markers=True,
        title="Deliveries per day",
    )
    fig_line.update_traces(line_color=COLORS["accent"])
    fig_line.update_layout(
        xaxis_title="Date", yaxis_title="Number of deliveries",
        hovermode="x unified", margin=dict(t=50),
    )
    st.plotly_chart(fig_line, width="stretch")
else:
    st.info("No deliveries in the selected range.")

# --------------------------------------------------------------------------- #
# Status mix by week (bar)
# --------------------------------------------------------------------------- #
st.subheader("Delivery outcomes by week")
if len(window):
    wk = window.copy()
    # Week label = the Monday of each ISO week, for clean chronological sorting.
    wk["week"] = wk["date"].dt.to_period("W").apply(lambda p: p.start_time.date())
    by_week = (
        wk.groupby(["week", "delivery_status"]).size().reset_index(name="count")
    )
    fig_bar = px.bar(
        by_week, x="week", y="count", color="delivery_status",
        title="On-time vs delayed vs cancelled vs failed, by week",
        color_discrete_map=COLORS,
        category_orders={"delivery_status": ["On Time", "Delayed", "Cancelled", "Failed"]},
    )
    fig_bar.update_layout(
        xaxis_title="Week starting", yaxis_title="Number of deliveries",
        legend_title="Status", barmode="stack", margin=dict(t=50),
    )
    st.plotly_chart(fig_bar, width="stretch")
else:
    st.info("No deliveries in the selected range.")
