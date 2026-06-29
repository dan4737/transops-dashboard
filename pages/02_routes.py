"""
02_routes.py — Route Performance
================================
Lane-level scorecard. For every route it shows total deliveries, on-time rate,
average delivery time, and average delay — then highlights the best lane in
green and the worst in red so an operations lead can immediately see where to
focus. Filterable by date range, origin city, and destination city.
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

page_setup("Route Performance", icon="🗺️")
page_header("🗺️ Route Performance", "Which lanes are winning — and which need attention")

# Minimum deliveries for a route to qualify as "best"/"worst" (avoids tiny
# samples skewing the ranking).
MIN_SAMPLE = 5

# --------------------------------------------------------------------------- #
# Data + filters
# --------------------------------------------------------------------------- #
deliveries = db.load_deliveries()
routes = db.load_routes()

# Attach origin / destination so we can filter by city.
deliveries = deliveries.merge(
    routes[["route_name", "origin_city", "destination_city"]],
    on="route_name", how="left",
)

start, end = date_range_filter(deliveries, key="routes", default_days=90)
st.sidebar.markdown("### 🏙️ Cities")
origins = multiselect_filter("Origin city", routes["origin_city"].unique(), "origin")
dests = multiselect_filter("Destination city", routes["destination_city"].unique(), "dest")

window = db.filter_by_date(deliveries, start, end)
window = window[
    window["origin_city"].isin(origins) & window["destination_city"].isin(dests)
]

st.caption(f"Showing **{start.date()} → {end.date()}** · {len(window):,} deliveries "
           f"across {window['route_name'].nunique()} routes.")

if window.empty:
    st.info("No deliveries match the current filters.")
    st.stop()


# --------------------------------------------------------------------------- #
# Per-route KPIs
# --------------------------------------------------------------------------- #
def route_kpis(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, g in df.groupby("route_name"):
        done = g.dropna(subset=["actual_departure", "actual_arrival"])
        avg_hours = (
            (done["actual_arrival"] - done["actual_departure"]).dt.total_seconds().mean()
            / 3600 if len(done) else 0
        )
        delayed = g[g["delivery_status"] == "Delayed"]
        rows.append(
            {
                "Route": name,
                "Origin": g["origin_city"].iloc[0],
                "Destination": g["destination_city"].iloc[0],
                "Deliveries": len(g),
                "On-time rate %": round(100 * g["is_on_time"].mean(), 1),
                "Avg delivery time (h)": round(avg_hours, 1),
                "Avg delay (min)": round(delayed["delay_minutes"].mean(), 0)
                if len(delayed) else 0,
            }
        )
    out = pd.DataFrame(rows).sort_values("On-time rate %", ascending=False)
    return out.reset_index(drop=True)


kpis = route_kpis(window)

# Identify best / worst among routes with a meaningful sample size.
qualified = kpis[kpis["Deliveries"] >= MIN_SAMPLE]
best_route = qualified.iloc[0]["Route"] if len(qualified) else None
worst_route = qualified.iloc[-1]["Route"] if len(qualified) else None

# --------------------------------------------------------------------------- #
# Highlight cards
# --------------------------------------------------------------------------- #
c1, c2 = st.columns(2)
if best_route is not None:
    b = qualified.iloc[0]
    c1.success(f"🏆 **Best route:** {best_route} — "
               f"{b['On-time rate %']:.1f}% on-time ({int(b['Deliveries'])} trips)")
    w = qualified.iloc[-1]
    c2.error(f"🚩 **Worst route:** {worst_route} — "
             f"{w['On-time rate %']:.1f}% on-time ({int(w['Deliveries'])} trips)")

st.divider()

# --------------------------------------------------------------------------- #
# Scorecard table (best green, worst red)
# --------------------------------------------------------------------------- #
st.subheader("Route scorecard")


def highlight_rows(row):
    if row["Route"] == best_route:
        return ["background-color: #E6F4EA"] * len(row)   # light green
    if row["Route"] == worst_route:
        return ["background-color: #FDE7E7"] * len(row)   # light red
    return [""] * len(row)


styled = (
    kpis.style
    .apply(highlight_rows, axis=1)
    .format({"On-time rate %": "{:.1f}", "Avg delivery time (h)": "{:.1f}",
             "Avg delay (min)": "{:.0f}"})
)
st.dataframe(styled, width="stretch", hide_index=True)
st.caption(f"Best/worst chosen among routes with ≥ {MIN_SAMPLE} deliveries in range.")

# --------------------------------------------------------------------------- #
# On-time rate by route (bar)
# --------------------------------------------------------------------------- #
st.subheader("On-time rate by route")
chart_df = kpis.copy()


def bar_color(route):
    if route == best_route:
        return COLORS["good"]
    if route == worst_route:
        return COLORS["bad"]
    return COLORS["accent"]


chart_df["color"] = chart_df["Route"].apply(bar_color)
fig = px.bar(
    chart_df.sort_values("On-time rate %"),
    x="On-time rate %", y="Route", orientation="h",
    title="On-time rate by route (best = green, worst = red)",
)
fig.update_traces(marker_color=chart_df.sort_values("On-time rate %")["color"])
fig.add_vline(x=70, line_dash="dash", line_color=COLORS["warning"],
              annotation_text="70% anomaly threshold")
fig.update_layout(xaxis_title="On-time rate (%)", yaxis_title="",
                  margin=dict(t=50), xaxis_range=[0, 100])
st.plotly_chart(fig, width="stretch")
