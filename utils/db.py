"""
db.py
=====
Database connection and query helpers for the TransOps dashboard.

Every Streamlit page imports from this module instead of touching SQLite
directly. Centralising access here means:

  * one place defines where the database lives,
  * date columns are parsed consistently into pandas datetimes,
  * results are cached so pages stay fast, and
  * the app can self-heal on a fresh deploy by generating the database if the
    .db file was not committed to the repo.

Swapping the data source later (e.g. a live TMS API) only requires changing the
`load_*` functions here -- the pages never need to know.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys

import pandas as pd

try:
    import streamlit as st
    _HAS_ST = True
except Exception:  # pragma: no cover - allows importing outside Streamlit
    _HAS_ST = False


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

# utils/ -> project root -> data/transport.db
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "transport.db")
GENERATOR = os.path.join(DATA_DIR, "generate_data.py")


# --------------------------------------------------------------------------- #
# Caching shim
# --------------------------------------------------------------------------- #
# Use st.cache_data when running inside Streamlit; fall back to a no-op
# decorator so the helpers remain usable from plain scripts and tests.

def _cache(ttl: int = 300):
    if _HAS_ST:
        return st.cache_data(ttl=ttl, show_spinner=False)

    def _identity(func):
        return func

    return _identity


# --------------------------------------------------------------------------- #
# Connection / bootstrap
# --------------------------------------------------------------------------- #

def ensure_database() -> None:
    """
    Make sure the SQLite database exists.

    On Streamlit Community Cloud the repo may be cloned without the .db file
    (it can be gitignored), so we regenerate it on first use. Safe to call on
    every page load -- it only does work when the file is missing.
    """
    if not os.path.exists(DB_PATH):
        subprocess.run([sys.executable, GENERATOR], check=True)


def get_connection() -> sqlite3.Connection:
    """Open a connection to the TMS database, generating it first if needed."""
    ensure_database()
    return sqlite3.connect(DB_PATH)


def run_query(sql: str, params: tuple | None = None) -> pd.DataFrame:
    """Run an arbitrary read query and return a DataFrame."""
    conn = get_connection()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


def execute(sql: str, params: tuple | None = None) -> None:
    """Run a write statement (INSERT/UPDATE/DELETE) and commit."""
    conn = get_connection()
    try:
        conn.execute(sql, params or ())
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Typed table loaders (cached)
# --------------------------------------------------------------------------- #

@_cache(ttl=300)
def load_deliveries() -> pd.DataFrame:
    """Deliveries fact table with datetime columns parsed."""
    df = run_query("SELECT * FROM deliveries")
    df["date"] = pd.to_datetime(df["date"])
    for col in [
        "scheduled_departure", "actual_departure",
        "scheduled_arrival", "actual_arrival",
    ]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # Derived helpers used across multiple pages.
    df["incidents_reported"] = df["incidents_reported"].astype(bool)
    df["is_on_time"] = df["delivery_status"] == "On Time"
    # Delay in minutes (only meaningful for completed trips with an arrival).
    df["delay_minutes"] = (
        (df["actual_arrival"] - df["scheduled_arrival"]).dt.total_seconds() / 60
    )
    df.loc[df["delay_minutes"] < 0, "delay_minutes"] = 0  # early arrivals = 0 delay
    return df


@_cache(ttl=300)
def load_vehicles() -> pd.DataFrame:
    """Vehicle fleet table with maintenance date parsed."""
    df = run_query("SELECT * FROM vehicles")
    df["last_maintenance_date"] = pd.to_datetime(df["last_maintenance_date"])
    today = pd.Timestamp.now().normalize()
    df["days_since_maintenance"] = (today - df["last_maintenance_date"]).dt.days
    df["maintenance_overdue"] = df["days_since_maintenance"] > 90
    return df


@_cache(ttl=300)
def load_routes() -> pd.DataFrame:
    """Routes master table."""
    return run_query("SELECT * FROM routes")


def load_anomalies() -> pd.DataFrame:
    """Triggered anomalies. Not cached -- this table changes at runtime."""
    df = run_query("SELECT * FROM anomalies ORDER BY date_triggered DESC")
    if not df.empty:
        df["date_triggered"] = pd.to_datetime(df["date_triggered"])
    return df


# --------------------------------------------------------------------------- #
# Anomaly table writers
# --------------------------------------------------------------------------- #

def clear_anomalies() -> None:
    """Empty the anomalies table (called before a fresh detection run)."""
    execute("DELETE FROM anomalies")


def insert_anomaly(
    rule: str,
    severity: str,
    description: str,
    entity_type: str,
    affected_entity: str,
    metric_value: float,
    date_triggered: str,
) -> None:
    """Insert a single detected anomaly."""
    execute(
        """
        INSERT INTO anomalies
            (rule, severity, description, entity_type,
             affected_entity, metric_value, date_triggered, resolved)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (rule, severity, description, entity_type,
         affected_entity, metric_value, date_triggered),
    )


def mark_anomaly_resolved(anomaly_id: int) -> None:
    """Flag an anomaly as resolved."""
    execute("UPDATE anomalies SET resolved = 1 WHERE anomaly_id = ?", (anomaly_id,))


# --------------------------------------------------------------------------- #
# Convenience filters
# --------------------------------------------------------------------------- #

def filter_by_date(df: pd.DataFrame, start, end, col: str = "date") -> pd.DataFrame:
    """Inclusive date-range filter used by the sidebar filters on every page."""
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)
    mask = (df[col] >= start) & (df[col] <= end + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))
    return df.loc[mask].copy()


if __name__ == "__main__":
    # Smoke test when run directly.
    ensure_database()
    d = load_deliveries()
    v = load_vehicles()
    r = load_routes()
    print(f"deliveries: {len(d)} rows, {d['date'].min().date()} -> {d['date'].max().date()}")
    print(f"vehicles:   {len(v)} rows, overdue maintenance: {int(v['maintenance_overdue'].sum())}")
    print(f"routes:     {len(r)} rows")
    print(f"on-time rate: {100 * d['is_on_time'].mean():.1f}%")
    print(f"avg delay (delayed trips): {d.loc[d.delay_minutes>0,'delay_minutes'].mean():.0f} min")
