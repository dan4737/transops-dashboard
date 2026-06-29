"""
05_reports.py — Automated Reports
=================================
One-click PDF reporting. Operations can generate a daily or weekly report on
demand (the same content the scheduler would email automatically), preview it
in-app, and download it. Reports include an executive summary, KPI table, top
issues, and an auto-generated recommendations section.
"""

import sys
import os
import base64

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

from utils.ui import page_setup, page_header
from utils import db
from utils import report_generator as rg

page_setup("Automated Reports", icon="📄")
page_header("📄 Automated Reports", "Generate, preview, and download daily & weekly PDF reports")

deliveries = db.load_deliveries()
latest = deliveries["date"].max()

st.info(
    "These are the same reports the scheduler produces automatically (daily at "
    "7am, weekly on Monday). Generate one on demand below.",
    icon="🗓️",
)

# --------------------------------------------------------------------------- #
# Generation buttons
# --------------------------------------------------------------------------- #
c1, c2 = st.columns(2)

with c1:
    st.markdown(f"#### 📅 Daily report\nFor **{latest.date():%A, %b %d, %Y}** (latest data day)")
    if st.button("Generate daily report", type="primary", width="stretch"):
        pdf, summary = rg.generate_daily_report(latest)
        st.session_state["report_pdf"] = pdf
        st.session_state["report_name"] = f"TransOps_Daily_{summary['date']}.pdf"
        st.session_state["report_summary"] = summary
        st.session_state["report_kind"] = "Daily"
        st.toast("Daily report generated", icon="✅")

with c2:
    week_start = (latest - pd.Timedelta(days=6)).date()
    st.markdown(f"#### 🗓️ Weekly report\nWeek of **{week_start:%b %d} – {latest.date():%b %d, %Y}**")
    if st.button("Generate weekly report", type="primary", width="stretch"):
        pdf, summary = rg.generate_weekly_report(latest)
        st.session_state["report_pdf"] = pdf
        st.session_state["report_name"] = f"TransOps_Weekly_{summary['end']}.pdf"
        st.session_state["report_summary"] = summary
        st.session_state["report_kind"] = "Weekly"
        st.toast("Weekly report generated", icon="✅")

st.divider()

# --------------------------------------------------------------------------- #
# Preview + download of the last generated report
# --------------------------------------------------------------------------- #
if "report_pdf" in st.session_state:
    kind = st.session_state["report_kind"]
    summary = st.session_state["report_summary"]
    pdf = st.session_state["report_pdf"]

    st.subheader(f"Last generated report — {kind}")

    # Quick summary chips.
    cols = st.columns(len(summary))
    for col, (k, v) in zip(cols, summary.items()):
        col.metric(k.replace("_", " ").title(), v)

    st.download_button(
        "⬇️ Download PDF",
        data=pdf,
        file_name=st.session_state["report_name"],
        mime="application/pdf",
        type="primary",
    )

    # In-app preview via an embedded PDF viewer (base64 data URI).
    with st.expander("📄 Preview report", expanded=True):
        b64 = base64.b64encode(pdf).decode("utf-8")
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" '
            f'width="100%" height="600" type="application/pdf" '
            f'style="border:1px solid #ddd;border-radius:6px;"></iframe>',
            unsafe_allow_html=True,
        )
        st.caption("If the inline preview is blocked by your browser, use the "
                   "download button above.")
else:
    st.caption("No report generated yet — use a button above to create one.")
