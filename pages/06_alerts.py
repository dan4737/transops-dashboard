"""
06_alerts.py — Anomaly Alerts
=============================
The early-warning board. Runs the rule-based anomaly engine, lists every
triggered anomaly with its severity, description, affected route/vehicle, and
trigger date — and lets an operator email the unresolved alerts to the team.

Anomaly rules (see utils/anomaly.py):
  1. Route on-time rate below 70% in the last 7 days
  2. Vehicle with 3+ incidents in 30 days
  3. Fleet delay rate spikes >20% vs the previous week
  4. Vehicle overdue for maintenance (90+ days)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from utils.ui import page_setup, page_header, SEVERITY_COLORS
from utils import db
from utils import anomaly
from utils import email_alert

page_setup("Anomaly Alerts", icon="🚨")
page_header("🚨 Anomaly Alerts", "Automated early-warning system for route, fleet, and incident risks")

# --------------------------------------------------------------------------- #
# Run detection (fresh on every load) and read back from the database.
# --------------------------------------------------------------------------- #
col_run, col_info = st.columns([1, 3])
with col_run:
    if st.button("🔄 Re-run detection", width="stretch"):
        st.cache_data.clear()

anomaly.detect_anomalies(persist=True)
df = db.load_anomalies()

with col_info:
    st.caption("Rules: route on-time <70% (7d) · vehicle 3+ incidents (30d) · "
               "delay spike >20% WoW · maintenance overdue (90d+)")

if df.empty:
    st.success("✅ No anomalies detected. All systems within normal ranges.")
    st.stop()

# --------------------------------------------------------------------------- #
# Severity KPIs
# --------------------------------------------------------------------------- #
sev_counts = df["severity"].value_counts()
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total anomalies", len(df))
k2.metric("🔴 High", int(sev_counts.get("High", 0)))
k3.metric("🟠 Medium", int(sev_counts.get("Medium", 0)))
k4.metric("🟡 Low", int(sev_counts.get("Low", 0)))

st.divider()

# --------------------------------------------------------------------------- #
# Filter + table
# --------------------------------------------------------------------------- #
st.sidebar.markdown("### 🚦 Severity")
sev_choice = st.sidebar.multiselect(
    "Show severities", ["High", "Medium", "Low"], default=[], key="sev")
severities = sev_choice if sev_choice else ["High", "Medium", "Low"]

view = df[df["severity"].isin(severities)].copy()
view["order"] = view["severity"].map(anomaly.SEVERITY_ORDER)
view = view.sort_values(["order", "date_triggered"], ascending=[True, False])

st.subheader("Triggered anomalies")
table = view[[
    "severity", "rule", "entity_type", "affected_entity",
    "description", "metric_value", "date_triggered", "resolved",
]].rename(columns={
    "severity": "Severity", "rule": "Rule", "entity_type": "Type",
    "affected_entity": "Affected", "description": "Description",
    "metric_value": "Value", "date_triggered": "Triggered", "resolved": "Resolved",
})
table["Triggered"] = table["Triggered"].dt.date
table["Resolved"] = table["Resolved"].map({0: "Open", 1: "Resolved"})


def color_severity(val):
    return f"color: {SEVERITY_COLORS.get(val, '#000')}; font-weight: bold"


styled = table.style.map(color_severity, subset=["Severity"])
st.dataframe(styled, width="stretch", hide_index=True)

st.divider()

# --------------------------------------------------------------------------- #
# Email alerting for unresolved anomalies
# --------------------------------------------------------------------------- #
st.subheader("📧 Alert notifications")
unresolved = df[df["resolved"] == 0]
st.write(f"**{len(unresolved)}** unresolved anomaly(ies) eligible for alerting.")

with st.expander("Preview alert contents"):
    st.text(email_alert.preview_alert_text(unresolved))

configured = email_alert.is_configured()
if not configured:
    st.info("ℹ️ Email is not configured. Add SMTP credentials in Streamlit "
            "secrets (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, "
            "ALERT_FROM, ALERT_TO) to enable live alerts. The button below "
            "will report configuration status until then.")

if st.button("📨 Send Alert Email", type="primary", disabled=unresolved.empty):
    ok, message = email_alert.send_alert_email(unresolved)
    if ok:
        st.success(message)
    else:
        st.warning(message)
