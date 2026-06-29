"""
04_incidents.py — Incident & Delay Analysis
============================================
Root-cause view. Breaks down what is going wrong and when:

  * Incidents by type (pie) — categorised by the delay reason behind them
  * Delay reasons breakdown (bar)
  * Full incident log (date, route, vehicle, description)
  * Delay-frequency trend over time (line)

Filterable by date range and delay reason.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.ui import page_setup, page_header, date_range_filter, COLORS
from utils import db

page_setup("Incident & Delay Analysis", icon="⚠️")
page_header("⚠️ Incident & Delay Analysis", "Root causes and trends behind delays and incidents")

REASON_COLORS = {
    "Traffic": COLORS["accent"],
    "Weather": "#5C6BC0",
    "Vehicle Breakdown": COLORS["bad"],
    "Driver Issue": COLORS["warning"],
}

# --------------------------------------------------------------------------- #
# Data + filters
# --------------------------------------------------------------------------- #
deliveries = db.load_deliveries()

start, end = date_range_filter(deliveries, key="incidents", default_days=90)
window = db.filter_by_date(deliveries, start, end)

# Delay-reason filter (only real reasons, not "None").
real_reasons = sorted(r for r in deliveries["delay_reason"].unique() if r != "None")
st.sidebar.markdown("### 🧭 Delay reason")
chosen = st.sidebar.multiselect("Reason", real_reasons, default=[], key="reason")
reasons = chosen if chosen else real_reasons

# Subsets used below.
delayed = window[window["delivery_status"].isin(["Delayed", "Failed"])]
delayed = delayed[delayed["delay_reason"].isin(reasons)]
incidents = window[window["incidents_reported"]]
incidents = incidents[incidents["delay_reason"].isin(reasons + ["None"])]

st.caption(f"Showing **{start.date()} → {end.date()}** · "
           f"{len(delayed):,} delayed/failed · {len(incidents):,} incidents.")

# --------------------------------------------------------------------------- #
# KPI row
# --------------------------------------------------------------------------- #
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total incidents", len(incidents))
k2.metric("Delayed / failed", len(delayed))
k3.metric("Breakdowns", int((delayed["delay_reason"] == "Vehicle Breakdown").sum()))
worst_reason = delayed["delay_reason"].mode()
k4.metric("Top delay cause", worst_reason.iloc[0] if len(worst_reason) else "—")

st.divider()

# --------------------------------------------------------------------------- #
# Incidents by type + delay reasons breakdown (side by side)
# --------------------------------------------------------------------------- #
col1, col2 = st.columns(2)

with col1:
    st.subheader("Incidents by type")
    if len(incidents):
        inc_by_type = incidents["delay_reason"].replace("None", "Other").value_counts().reset_index()
        inc_by_type.columns = ["Type", "Count"]
        fig_pie = px.pie(inc_by_type, names="Type", values="Count", hole=0.4,
                         title="Reported incidents by cause",
                         color="Type", color_discrete_map=REASON_COLORS)
        fig_pie.update_traces(textinfo="label+percent")
        fig_pie.update_layout(margin=dict(t=50))
        st.plotly_chart(fig_pie, width="stretch")
    else:
        st.info("No incidents in range.")

with col2:
    st.subheader("Delay reasons breakdown")
    if len(delayed):
        by_reason = delayed["delay_reason"].value_counts().reset_index()
        by_reason.columns = ["Reason", "Count"]
        fig_bar = px.bar(by_reason, x="Reason", y="Count",
                         title="Delays by reason", color="Reason",
                         color_discrete_map=REASON_COLORS)
        fig_bar.update_layout(xaxis_title="Delay reason", yaxis_title="Number of delays",
                              showlegend=False, margin=dict(t=50))
        st.plotly_chart(fig_bar, width="stretch")
    else:
        st.info("No delays in range.")

st.divider()

# --------------------------------------------------------------------------- #
# Delay frequency trend
# --------------------------------------------------------------------------- #
st.subheader("Delay frequency over time")
if len(delayed):
    trend = (
        delayed.groupby(delayed["date"].dt.date).size().reset_index(name="Delays")
        .rename(columns={"date": "Date"})
    )
    fig_trend = px.area(trend, x="Date", y="Delays", title="Delayed / failed deliveries per day")
    fig_trend.update_traces(line_color=COLORS["bad"], fillcolor="rgba(198,40,40,0.15)")
    fig_trend.update_layout(xaxis_title="Date", yaxis_title="Number of delays",
                            hovermode="x unified", margin=dict(t=50))
    st.plotly_chart(fig_trend, width="stretch")
else:
    st.info("No delays in range.")

# --------------------------------------------------------------------------- #
# Incident log
# --------------------------------------------------------------------------- #
st.subheader("Incident log")
if len(incidents):
    log = incidents.sort_values("date", ascending=False)[[
        "date", "route_name", "vehicle_id", "delay_reason", "incident_description",
    ]].rename(columns={
        "date": "Date", "route_name": "Route", "vehicle_id": "Vehicle",
        "delay_reason": "Cause", "incident_description": "Description",
    }).copy()
    log["Date"] = log["Date"].dt.date
    st.dataframe(log, width="stretch", hide_index=True)
else:
    st.info("No incidents to show for the current filters.")
