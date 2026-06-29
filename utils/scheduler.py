"""
scheduler.py
============
Lightweight background scheduling, as called for in the brief (APScheduler
running inside the Streamlit app). It:

  * refreshes anomaly detection every hour,
  * generates the daily PDF report at 07:00, and
  * generates the weekly PDF report on Monday at 07:00,

writing the PDFs to data/reports/ so they are always ready.

The scheduler is started once per server process via st.cache_resource. Note:
on Streamlit Community Cloud the app sleeps when idle, so background jobs only
run while the app is awake — the on-demand buttons on the Reports page are the
reliable path for a live demo. This module shows the production-style
automation that would run against an always-on TMS feed.
"""

from __future__ import annotations

import os

try:
    import streamlit as st
    _HAS_ST = True
except Exception:  # pragma: no cover
    _HAS_ST = False

from utils import anomaly
from utils import report_generator as rg

REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "reports"
)


def _job_refresh_anomalies() -> None:
    try:
        anomaly.detect_anomalies(persist=True)
    except Exception:  # never let a job crash the scheduler
        pass


def _job_daily_report() -> None:
    try:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        pdf, summary = rg.generate_daily_report()
        with open(os.path.join(REPORTS_DIR, f"daily_{summary['date']}.pdf"), "wb") as f:
            f.write(pdf)
    except Exception:
        pass


def _job_weekly_report() -> None:
    try:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        pdf, summary = rg.generate_weekly_report()
        with open(os.path.join(REPORTS_DIR, f"weekly_{summary['end']}.pdf"), "wb") as f:
            f.write(pdf)
    except Exception:
        pass


def _create_scheduler():
    """Build and start a BackgroundScheduler with all jobs registered."""
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(_job_refresh_anomalies, CronTrigger(minute=0),
                      id="anomalies", replace_existing=True)
    scheduler.add_job(_job_daily_report, CronTrigger(hour=7, minute=0),
                      id="daily_report", replace_existing=True)
    scheduler.add_job(_job_weekly_report, CronTrigger(day_of_week="mon", hour=7, minute=0),
                      id="weekly_report", replace_existing=True)
    scheduler.start()
    return scheduler


def start_scheduler():
    """
    Start the background scheduler exactly once per server process.

    Uses st.cache_resource so repeated Streamlit reruns don't spawn duplicate
    schedulers. Returns the scheduler (or None if it could not start).
    """
    if _HAS_ST:
        @st.cache_resource(show_spinner=False)
        def _cached():
            try:
                return _create_scheduler()
            except Exception:
                return None
        return _cached()
    return _create_scheduler()
