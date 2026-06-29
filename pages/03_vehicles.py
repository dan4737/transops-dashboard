"""
03_vehicles.py — Vehicle Management
===================================
Fleet health board. Lists every vehicle with its current status, utilisation,
trips in the selected period, and last maintenance date — flagging in red any
unit that has not been serviced in over 90 days. A status pie chart shows how
the fleet is currently deployed. Filterable by vehicle type and date range
(the date range drives utilisation / trip counts).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.ui import (
    page_setup, page_header, date_range_filter, multiselect_filter, COLORS,
)
from utils import db

page_setup("Vehicle Management", icon="🚛")
page_header("🚛 Vehicle Management", "Fleet status, utilisation, and maintenance flags")

STATUS_COLORS = {
    "Available": COLORS["good"],
    "In Transit": COLORS["accent"],
    "Under Maintenance": COLORS["warning"],
}

# --------------------------------------------------------------------------- #
# Data + filters
# --------------------------------------------------------------------------- #
vehicles = db.load_vehicles()
deliveries = db.load_deliveries()

start, end = date_range_filter(deliveries, key="vehicles", default_days=30)
st.sidebar.markdown("### 🚚 Vehicle type")
types = multiselect_filter("Type", vehicles["vehicle_type"].unique(), "vtype")

fleet = vehicles[vehicles["vehicle_type"].isin(types)].copy()
window = db.filter_by_date(deliveries, start, end)
window_days = max((end - start).days + 1, 1)

# --------------------------------------------------------------------------- #
# Per-vehicle utilisation = distinct active days / days in window.
# --------------------------------------------------------------------------- #
active_days = (
    window.groupby("vehicle_id")["date"]
    .apply(lambda s: s.dt.normalize().nunique())
    .to_dict()
)
trips = window.groupby("vehicle_id")["delivery_id"].count().to_dict()

fleet["Trips (in range)"] = fleet["vehicle_id"].map(trips).fillna(0).astype(int)
fleet["Utilisation %"] = (
    fleet["vehicle_id"].map(active_days).fillna(0) / window_days * 100
).clip(upper=100).round(0)

# --------------------------------------------------------------------------- #
# KPI row
# --------------------------------------------------------------------------- #
k1, k2, k3, k4 = st.columns(4)
k1.metric("Fleet size", len(fleet))
k2.metric("In transit", int((fleet["current_status"] == "In Transit").sum()))
k3.metric("Under maintenance", int((fleet["current_status"] == "Under Maintenance").sum()))
k4.metric("Maintenance overdue", int(fleet["maintenance_overdue"].sum()),
          help="Not serviced in over 90 days")

overdue_n = int(fleet["maintenance_overdue"].sum())
if overdue_n:
    overdue_ids = ", ".join(fleet.loc[fleet["maintenance_overdue"], "vehicle_id"])
    st.error(f"🔴 {overdue_n} vehicle(s) overdue for maintenance: {overdue_ids}")

st.divider()

# --------------------------------------------------------------------------- #
# Fleet table (overdue rows in red)
# --------------------------------------------------------------------------- #
st.subheader("Fleet roster")
table = fleet[[
    "vehicle_id", "vehicle_type", "plate_number", "current_status",
    "Utilisation %", "Trips (in range)", "last_maintenance_date",
    "days_since_maintenance",
]].rename(columns={
    "vehicle_id": "Vehicle", "vehicle_type": "Type", "plate_number": "Plate",
    "current_status": "Status", "last_maintenance_date": "Last maintenance",
    "days_since_maintenance": "Days since service",
}).copy()
table["Last maintenance"] = pd.to_datetime(table["Last maintenance"]).dt.date

overdue_mask = table["Days since service"] > 90


def highlight_overdue(row):
    is_overdue = row["Days since service"] > 90
    return ["background-color: #FDE7E7" if is_overdue else ""] * len(row)


styled = (
    table.sort_values("Days since service", ascending=False).style
    .apply(highlight_overdue, axis=1)
    .format({"Utilisation %": "{:.0f}", "Days since service": "{:.0f}"})
)
st.dataframe(styled, width="stretch", hide_index=True)
st.caption("Rows in red have not been serviced in over 90 days.")

# --------------------------------------------------------------------------- #
# Status distribution (pie)
# --------------------------------------------------------------------------- #
st.subheader("Fleet status distribution")
status_counts = fleet["current_status"].value_counts().reset_index()
status_counts.columns = ["Status", "Count"]
fig = px.pie(
    status_counts, names="Status", values="Count", hole=0.45,
    title="Current vehicle status",
    color="Status", color_discrete_map=STATUS_COLORS,
)
fig.update_traces(textinfo="label+percent")
fig.update_layout(margin=dict(t=50))
st.plotly_chart(fig, width="stretch")
