"""
anomaly.py
==========
Rule-based anomaly detection engine. This is the "early-warning system" that
flags operational problems before a manager has to go looking for them.

Four rules, straight from the project brief:

  Rule 1  Route on-time rate below 70% in the last 7 days
  Rule 2  Vehicle with 3+ incidents in the last 30 days
  Rule 3  Fleet delay rate spikes >20% vs the previous week
  Rule 4  Vehicle overdue for maintenance (90+ days)

`detect_anomalies()` runs all rules and, by default, persists the results to
the `anomalies` table in SQLite so the Alerts page and reports can read them.
"""

from __future__ import annotations

import pandas as pd

from utils import db

# Tuning constants (kept here so the rules are easy to explain/adjust).
ON_TIME_THRESHOLD = 70        # Rule 1: % on-time floor
MIN_ROUTE_SAMPLE = 3          # Rule 1: ignore routes with too few recent trips
INCIDENT_THRESHOLD = 3        # Rule 2: incidents in 30 days
SPIKE_THRESHOLD_PCT = 20      # Rule 3: relative delay-rate increase
MAINT_OVERDUE_DAYS = 90       # Rule 4: days since last service


def _delay_rate(df: pd.DataFrame) -> float:
    if not len(df):
        return 0.0
    return 100 * df["delivery_status"].isin(["Delayed", "Failed"]).mean()


def detect_anomalies(persist: bool = True) -> pd.DataFrame:
    """
    Run all anomaly rules against the current data.

    Returns a DataFrame of detected anomalies. When `persist` is True the
    anomalies table is cleared and repopulated with the fresh results.
    """
    deliveries = db.load_deliveries()
    vehicles = db.load_vehicles()

    latest = deliveries["date"].max()
    today_iso = latest.date().isoformat()
    anomalies: list[dict] = []

    # ---- Rule 1: route on-time rate < 70% in last 7 days ------------------ #
    last7 = deliveries[deliveries["date"] > latest - pd.Timedelta(days=7)]
    for route, g in last7.groupby("route_name"):
        if len(g) < MIN_ROUTE_SAMPLE:
            continue
        rate = 100 * g["is_on_time"].mean()
        if rate < ON_TIME_THRESHOLD:
            severity = "High" if rate < 50 else "Medium"
            anomalies.append({
                "rule": "Route on-time < 70% (7d)",
                "severity": severity,
                "description": (f"Route '{route}' on-time rate is {rate:.0f}% over the "
                                f"last 7 days ({len(g)} trips), below the 70% threshold."),
                "entity_type": "Route",
                "affected_entity": route,
                "metric_value": round(rate, 1),
                "date_triggered": today_iso,
            })

    # ---- Rule 2: vehicle with 3+ incidents in 30 days --------------------- #
    last30 = deliveries[deliveries["date"] > latest - pd.Timedelta(days=30)]
    inc = last30[last30["incidents_reported"]].groupby("vehicle_id").size()
    for vehicle, count in inc.items():
        if count >= INCIDENT_THRESHOLD:
            severity = "High" if count >= 5 else "Medium"
            anomalies.append({
                "rule": "Vehicle 3+ incidents (30d)",
                "severity": severity,
                "description": (f"Vehicle {vehicle} logged {int(count)} incidents in the "
                                f"last 30 days (threshold {INCIDENT_THRESHOLD})."),
                "entity_type": "Vehicle",
                "affected_entity": vehicle,
                "metric_value": float(count),
                "date_triggered": today_iso,
            })

    # ---- Rule 3: fleet delay rate spike > 20% vs previous week ------------ #
    this_week = deliveries[deliveries["date"] > latest - pd.Timedelta(days=7)]
    prev_week = deliveries[
        (deliveries["date"] <= latest - pd.Timedelta(days=7))
        & (deliveries["date"] > latest - pd.Timedelta(days=14))
    ]
    this_rate, prev_rate = _delay_rate(this_week), _delay_rate(prev_week)
    if prev_rate > 0:
        rel_change = (this_rate - prev_rate) / prev_rate * 100
        if rel_change > SPIKE_THRESHOLD_PCT and (this_rate - prev_rate) >= 5:
            severity = "High" if rel_change > 40 else "Medium"
            anomalies.append({
                "rule": "Delay rate spike > 20% (WoW)",
                "severity": severity,
                "description": (f"Fleet delay rate rose to {this_rate:.0f}% this week from "
                                f"{prev_rate:.0f}% last week (+{rel_change:.0f}% relative)."),
                "entity_type": "Fleet",
                "affected_entity": "All routes",
                "metric_value": round(rel_change, 1),
                "date_triggered": today_iso,
            })

    # ---- Rule 4: vehicle overdue for maintenance (90+ days) --------------- #
    overdue = vehicles[vehicles["days_since_maintenance"] > MAINT_OVERDUE_DAYS]
    for _, v in overdue.iterrows():
        days = int(v["days_since_maintenance"])
        severity = "High" if days > 120 else "Medium"
        anomalies.append({
            "rule": "Maintenance overdue (90+ days)",
            "severity": severity,
            "description": (f"Vehicle {v['vehicle_id']} ({v['vehicle_type']}) last serviced "
                            f"{days} days ago — overdue for maintenance."),
            "entity_type": "Vehicle",
            "affected_entity": v["vehicle_id"],
            "metric_value": float(days),
            "date_triggered": today_iso,
        })

    result = pd.DataFrame(anomalies)

    if persist:
        db.clear_anomalies()
        for a in anomalies:
            db.insert_anomaly(
                rule=a["rule"], severity=a["severity"], description=a["description"],
                entity_type=a["entity_type"], affected_entity=a["affected_entity"],
                metric_value=a["metric_value"], date_triggered=a["date_triggered"],
            )

    return result


# Severity ordering helper for sorting/colour.
SEVERITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}


if __name__ == "__main__":
    df = detect_anomalies(persist=True)
    print(f"Detected {len(df)} anomalies")
    if len(df):
        print(df.groupby(["rule", "severity"]).size().to_string())
