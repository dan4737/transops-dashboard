"""
email_alert.py
==============
Sends anomaly alert notifications by email over SMTP.

Configuration is read from Streamlit secrets (`.streamlit/secrets.toml` locally
or the Secrets manager on Streamlit Cloud) with environment-variable fallback,
so no credentials ever live in the code. Expected keys:

    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_FROM, ALERT_TO

The functions never raise on missing configuration — they return a
(success, message) tuple so the UI can show a friendly status instead of
crashing. This keeps the public demo fully functional even with no mail server
configured.
"""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd

try:
    import streamlit as st
    _HAS_ST = True
except Exception:  # pragma: no cover
    _HAS_ST = False

REQUIRED_KEYS = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "ALERT_FROM", "ALERT_TO"]


def _get(key: str, default: str | None = None) -> str | None:
    """Read a config value from st.secrets first, then environment."""
    if _HAS_ST:
        try:
            if key in st.secrets:
                return str(st.secrets[key])
        except Exception:
            pass
    return os.environ.get(key, default)


def is_configured() -> bool:
    """True only if every required SMTP setting is present."""
    return all(_get(k) for k in REQUIRED_KEYS)


def _build_html(anomalies: pd.DataFrame) -> str:
    """Render the unresolved anomalies as a simple HTML email body."""
    rows = ""
    for _, a in anomalies.iterrows():
        color = {"High": "#C62828", "Medium": "#EF6C00", "Low": "#F9A825"}.get(
            a["severity"], "#555")
        rows += (
            f"<tr>"
            f"<td style='padding:6px;color:{color};font-weight:bold'>{a['severity']}</td>"
            f"<td style='padding:6px'>{a['rule']}</td>"
            f"<td style='padding:6px'>{a['affected_entity']}</td>"
            f"<td style='padding:6px'>{a['description']}</td>"
            f"</tr>"
        )
    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#1A1A2E">
      <h2 style="color:#1565C0">🚨 TransOps Anomaly Alert</h2>
      <p>{len(anomalies)} unresolved anomaly(ies) require attention:</p>
      <table style="border-collapse:collapse;width:100%">
        <tr style="background:#1565C0;color:#fff">
          <th style="padding:6px;text-align:left">Severity</th>
          <th style="padding:6px;text-align:left">Rule</th>
          <th style="padding:6px;text-align:left">Affected</th>
          <th style="padding:6px;text-align:left">Description</th>
        </tr>
        {rows}
      </table>
      <p style="color:#888;font-size:12px">Generated automatically by the TransOps dashboard.</p>
    </body></html>
    """


def send_alert_email(anomalies: pd.DataFrame, recipient: str | None = None) -> tuple[bool, str]:
    """
    Email the given unresolved anomalies.

    Returns (success, message). Returns a friendly failure (not an exception)
    when SMTP is not configured or sending fails.
    """
    if anomalies is None or anomalies.empty:
        return False, "No unresolved anomalies to send."

    if not is_configured():
        missing = [k for k in REQUIRED_KEYS if not _get(k)]
        return False, (
            "Email is not configured. Add SMTP settings in Streamlit secrets to "
            f"enable alerts (missing: {', '.join(missing)})."
        )

    host = _get("SMTP_HOST")
    port = int(_get("SMTP_PORT", "587"))
    user = _get("SMTP_USER")
    password = _get("SMTP_PASSWORD")
    sender = _get("ALERT_FROM")
    to_addr = recipient or _get("ALERT_TO")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[TransOps] {len(anomalies)} unresolved anomaly alert(s)"
    msg["From"] = sender
    msg["To"] = to_addr
    msg.attach(MIMEText(_build_html(anomalies), "html"))

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(sender, [to_addr], msg.as_string())
        return True, f"Alert email sent to {to_addr}."
    except Exception as exc:  # pragma: no cover - network dependent
        return False, f"Failed to send email: {exc}"


def preview_alert_text(anomalies: pd.DataFrame) -> str:
    """Plain-text preview of what would be emailed (shown in the UI)."""
    if anomalies is None or anomalies.empty:
        return "No unresolved anomalies."
    lines = [f"{len(anomalies)} unresolved anomaly(ies):", ""]
    for _, a in anomalies.iterrows():
        lines.append(f"[{a['severity']}] {a['rule']} — {a['affected_entity']}: {a['description']}")
    return "\n".join(lines)
