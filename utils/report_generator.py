"""
report_generator.py
====================
Generates polished PDF operations reports (daily and weekly) entirely in
memory and returns them as bytes, ready for a Streamlit download button.

Built on ReportLab's Platypus layout engine plus its native graphics charts,
so there is **no dependency on a browser/Kaleido/matplotlib** for embedded
charts — important for a clean Streamlit Community Cloud deploy.

Each report contains an executive summary, a KPI table, the top issues, and an
auto-generated recommendations section derived from the data patterns. The
weekly report additionally embeds a chart and a week-over-week comparison.
"""

from __future__ import annotations

import io
from datetime import timedelta

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

from utils import db

BRAND_BLUE = colors.HexColor("#1565C0")
GOOD = colors.HexColor("#2E7D32")
BAD = colors.HexColor("#C62828")
LIGHT = colors.HexColor("#F4F6F9")


# --------------------------------------------------------------------------- #
# Styles
# --------------------------------------------------------------------------- #

def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("BrandTitle", parent=s["Title"], textColor=BRAND_BLUE, fontSize=22))
    s.add(ParagraphStyle("Section", parent=s["Heading2"], textColor=BRAND_BLUE,
                          fontSize=13, spaceBefore=12, spaceAfter=4))
    s.add(ParagraphStyle("Body", parent=s["BodyText"], fontSize=10, leading=14, alignment=TA_LEFT))
    s.add(ParagraphStyle("Small", parent=s["BodyText"], fontSize=8, textColor=colors.grey))
    return s


def _kpi_table(rows, col_widths=None):
    """A two-column label/value KPI table."""
    t = Table(rows, colWidths=col_widths or [3.2 * inch, 2.8 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _data_table(header, body):
    """A generic multi-column data table with a branded header row."""
    data = [header] + body
    t = Table(data, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


# --------------------------------------------------------------------------- #
# Metric helpers
# --------------------------------------------------------------------------- #

def _on_time(df):
    return 100 * df["is_on_time"].mean() if len(df) else 0.0


def _avg_hours(df):
    done = df.dropna(subset=["actual_departure", "actual_arrival"])
    if not len(done):
        return 0.0
    return (done["actual_arrival"] - done["actual_departure"]).dt.total_seconds().mean() / 3600


def _route_ranking(df):
    rows = []
    for name, g in df.groupby("route_name"):
        rows.append((name, len(g), _on_time(g)))
    rank = pd.DataFrame(rows, columns=["route", "n", "on_time"])
    return rank.sort_values("on_time", ascending=False).reset_index(drop=True)


def _recommendations(df, vehicles):
    """Auto-generate recommendations from the data patterns in `df`."""
    recs = []
    ot = _on_time(df)
    if ot < 80:
        recs.append(f"On-time performance is {ot:.0f}%, below the 80% target — "
                    "add schedule buffers on the highest-delay lanes.")

    rank = _route_ranking(df)
    weak = rank[(rank["n"] >= 5) & (rank["on_time"] < 70)]
    for _, r in weak.iterrows():
        recs.append(f"Route '{r['route']}' is underperforming at {r['on_time']:.0f}% "
                    "on-time — investigate carrier, traffic windows, and scheduling.")

    delayed = df[df["delivery_status"].isin(["Delayed", "Failed"])]
    if len(delayed):
        top_cause = delayed["delay_reason"].mode().iloc[0]
        if top_cause == "Vehicle Breakdown":
            recs.append("Vehicle breakdowns are the leading delay cause — bring "
                        "forward preventive maintenance on high-mileage units.")
        elif top_cause == "Weather":
            recs.append("Weather is the leading delay cause — build weather "
                        "contingency into customer ETAs this period.")
        elif top_cause == "Traffic":
            recs.append("Traffic is the leading delay cause — consider shifting "
                        "departures outside peak congestion windows.")

    overdue = vehicles[vehicles["maintenance_overdue"]]
    if len(overdue):
        ids = ", ".join(overdue["vehicle_id"])
        recs.append(f"Schedule maintenance immediately for overdue vehicles: {ids}.")

    if not recs:
        recs.append("Operations are within target ranges — maintain current cadence.")
    return recs


def _top_issues(df, vehicles):
    """A short bullet list of the most pressing problems."""
    issues = []
    rank = _route_ranking(df)
    weak = rank[(rank["n"] >= 5)].tail(3)
    for _, r in weak[weak["on_time"] < 80].iterrows():
        issues.append(f"{r['route']} at {r['on_time']:.0f}% on-time ({int(r['n'])} trips)")

    inc_by_vehicle = (
        df[df["incidents_reported"]].groupby("vehicle_id").size().sort_values(ascending=False)
    )
    if len(inc_by_vehicle) and inc_by_vehicle.iloc[0] >= 3:
        v = inc_by_vehicle.index[0]
        issues.append(f"Vehicle {v} logged {int(inc_by_vehicle.iloc[0])} incidents")

    overdue = vehicles[vehicles["maintenance_overdue"]]
    if len(overdue):
        issues.append(f"{len(overdue)} vehicle(s) overdue for maintenance")

    return issues[:3] if issues else ["No critical issues detected"]


# --------------------------------------------------------------------------- #
# Embedded chart (weekly)
# --------------------------------------------------------------------------- #

def _status_bar_drawing(df):
    """A native ReportLab bar chart of status counts (no external renderer)."""
    counts = df["delivery_status"].value_counts()
    order = ["On Time", "Delayed", "Cancelled", "Failed"]
    values = [int(counts.get(s, 0)) for s in order]

    d = Drawing(440, 200)
    chart = VerticalBarChart()
    chart.x, chart.y, chart.width, chart.height = 40, 25, 360, 150
    chart.data = [values]
    chart.categoryAxis.categoryNames = order
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(values) * 1.15 if max(values) else 1
    chart.bars[0].fillColor = BRAND_BLUE
    chart.barWidth = 14
    d.add(chart)
    return d


# --------------------------------------------------------------------------- #
# Public report builders
# --------------------------------------------------------------------------- #

def _build_pdf(flowables) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                            leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                            title="TransOps Operations Report")
    doc.build(flowables)
    buf.seek(0)
    return buf.read()


def generate_daily_report(as_of: pd.Timestamp | None = None) -> tuple[bytes, dict]:
    """Build the daily operations PDF for `as_of` (defaults to latest data day)."""
    s = _styles()
    deliveries = db.load_deliveries()
    vehicles = db.load_vehicles()

    if as_of is None:
        as_of = deliveries["date"].max()
    as_of = pd.Timestamp(as_of).normalize()
    day = deliveries[deliveries["date"] == as_of]

    scheduled = len(day)
    completed = int((day["delivery_status"] == "On Time").sum()
                    + (day["delivery_status"] == "Delayed").sum())
    on_time = _on_time(day)
    delays = int(day["delivery_status"].isin(["Delayed", "Failed"]).sum())
    incidents = int(day["incidents_reported"].sum())
    in_use = int((vehicles["current_status"] == "In Transit").sum())
    available = int((vehicles["current_status"] == "Available").sum())
    rank = _route_ranking(day)
    top_route = rank.iloc[0]["route"] if len(rank) else "—"

    flow = []
    flow.append(Paragraph("TransOps — Daily Operations Report", s["BrandTitle"]))
    flow.append(Paragraph(f"Reporting date: {as_of.date():%A, %B %d, %Y}", s["Small"]))
    flow.append(HRFlowable(width="100%", thickness=1, color=BRAND_BLUE))
    flow.append(Spacer(1, 10))

    flow.append(Paragraph("Executive Summary", s["Section"]))
    flow.append(Paragraph(
        f"{scheduled} deliveries were scheduled, of which {completed} ran "
        f"({on_time:.0f}% on-time). {delays} experienced delays and {incidents} "
        f"incident(s) were logged. The fleet had {in_use} vehicles in transit and "
        f"{available} available.", s["Body"]))
    flow.append(Spacer(1, 6))

    flow.append(Paragraph("Key Metrics", s["Section"]))
    flow.append(_kpi_table([
        ["Metric", "Value"],
        ["Deliveries scheduled", str(scheduled)],
        ["Deliveries completed", str(completed)],
        ["On-time rate", f"{on_time:.1f}%"],
        ["Delays / failures", str(delays)],
        ["Incidents reported", str(incidents)],
        ["Vehicles in use vs available", f"{in_use} / {available}"],
        ["Top performing route", top_route],
    ]))

    flow.append(Paragraph("Open Issues", s["Section"]))
    for issue in _top_issues(day, vehicles):
        flow.append(Paragraph(f"• {issue}", s["Body"]))

    flow.append(Paragraph("Recommendations", s["Section"]))
    for rec in _recommendations(day, vehicles):
        flow.append(Paragraph(f"• {rec}", s["Body"]))

    flow.append(Spacer(1, 16))
    flow.append(Paragraph("Generated automatically by the TransOps dashboard.", s["Small"]))

    summary = {"date": as_of.date().isoformat(), "scheduled": scheduled,
               "on_time": round(on_time, 1), "incidents": incidents}
    return _build_pdf(flow), summary


def generate_weekly_report(as_of: pd.Timestamp | None = None) -> tuple[bytes, dict]:
    """Build the weekly operations PDF for the 7 days ending `as_of`."""
    s = _styles()
    deliveries = db.load_deliveries()
    vehicles = db.load_vehicles()

    if as_of is None:
        as_of = deliveries["date"].max()
    end = pd.Timestamp(as_of).normalize()
    start = end - timedelta(days=6)
    prev_start, prev_end = start - timedelta(days=7), start - timedelta(days=1)

    week = deliveries[(deliveries["date"] >= start) & (deliveries["date"] <= end)]
    prev = deliveries[(deliveries["date"] >= prev_start) & (deliveries["date"] <= prev_end)]

    ot, ot_prev = _on_time(week), _on_time(prev)
    avg_h = _avg_hours(week)
    incidents = int(week["incidents_reported"].sum())
    util = 100 * week["vehicle_id"].nunique() / len(vehicles) if len(vehicles) else 0

    flow = []
    flow.append(Paragraph("TransOps — Weekly Operations Report", s["BrandTitle"]))
    flow.append(Paragraph(f"Week of {start.date():%b %d} – {end.date():%b %d, %Y}", s["Small"]))
    flow.append(HRFlowable(width="100%", thickness=1, color=BRAND_BLUE))
    flow.append(Spacer(1, 10))

    flow.append(Paragraph("Week Summary", s["Section"]))
    flow.append(Paragraph(
        f"{len(week)} deliveries ran this week at {ot:.0f}% on-time "
        f"({ot - ot_prev:+.0f} pts vs the prior week). Average delivery time was "
        f"{avg_h:.1f} hours, fleet utilisation {util:.0f}%, and {incidents} "
        f"incident(s) were recorded.", s["Body"]))

    flow.append(Paragraph("KPI Table", s["Section"]))
    flow.append(_kpi_table([
        ["KPI", "Value"],
        ["On-time rate", f"{ot:.1f}%"],
        ["Avg delivery time", f"{avg_h:.1f} h"],
        ["Vehicle utilisation", f"{util:.0f}%"],
        ["Incident count", str(incidents)],
        ["Total deliveries", str(len(week))],
    ]))

    flow.append(Paragraph("Week-over-Week Comparison", s["Section"]))
    flow.append(_data_table(
        ["Metric", "This week", "Last week", "Change"],
        [
            ["Deliveries", str(len(week)), str(len(prev)), f"{len(week) - len(prev):+d}"],
            ["On-time rate", f"{ot:.0f}%", f"{ot_prev:.0f}%", f"{ot - ot_prev:+.0f} pts"],
            ["Incidents", str(incidents), str(int(prev['incidents_reported'].sum())),
             f"{incidents - int(prev['incidents_reported'].sum()):+d}"],
        ],
    ))

    flow.append(Paragraph("Route Performance Ranking", s["Section"]))
    rank = _route_ranking(week)
    body = [[r["route"], str(int(r["n"])), f"{r['on_time']:.0f}%"]
            for _, r in rank.head(8).iterrows()]
    flow.append(_data_table(["Route", "Deliveries", "On-time"], body))

    flow.append(Paragraph("Top 3 Issues of the Week", s["Section"]))
    for issue in _top_issues(week, vehicles):
        flow.append(Paragraph(f"• {issue}", s["Body"]))

    flow.append(Paragraph("Delivery Outcomes", s["Section"]))
    flow.append(_status_bar_drawing(week))

    flow.append(Paragraph("Recommendations", s["Section"]))
    for rec in _recommendations(week, vehicles):
        flow.append(Paragraph(f"• {rec}", s["Body"]))

    flow.append(Spacer(1, 14))
    flow.append(Paragraph("Generated automatically by the TransOps dashboard.", s["Small"]))

    summary = {"start": start.date().isoformat(), "end": end.date().isoformat(),
               "on_time": round(ot, 1), "deliveries": len(week)}
    return _build_pdf(flow), summary


if __name__ == "__main__":
    daily, ds = generate_daily_report()
    weekly, ws = generate_weekly_report()
    with open("data/_sample_daily.pdf", "wb") as f:
        f.write(daily)
    with open("data/_sample_weekly.pdf", "wb") as f:
        f.write(weekly)
    print("daily:", len(daily), "bytes", ds)
    print("weekly:", len(weekly), "bytes", ws)
