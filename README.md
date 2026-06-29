# 🚚 TransOps — Transportation Intelligence Dashboard

An automated transportation intelligence dashboard that simulates a Transport
Management System (TMS), processes 90 days of delivery data, tracks operational
KPIs, detects anomalies, and generates automated PDF reports.

Built as a portfolio piece for a **Supply Chain Analyst / Transportation
Coordinator** role — it looks and behaves like an internal logistics tool a
real operations team would use every morning.

---

## ✨ Features

| Page | What it does |
|------|--------------|
| **📊 Executive Overview** | Week-over-week KPIs, daily volume trend, weekly status mix |
| **🗺️ Route Performance** | Per-lane scorecard, best/worst route highlighting, city filters |
| **🚛 Vehicle Management** | Fleet roster, utilisation, maintenance-overdue flags, status pie |
| **⚠️ Incident & Delay Analysis** | Root-cause pie/bar, delay trend, full incident log |
| **📄 Automated Reports** | One-click daily & weekly PDF reports with preview + download |
| **🚨 Anomaly Alerts** | Rule-based early-warning engine + email alerting |

### Anomaly rules
1. Route on-time rate below **70%** in the last 7 days
2. Vehicle with **3+ incidents** in 30 days
3. Fleet delay rate **spikes >20%** vs the previous week
4. Vehicle **overdue for maintenance** (90+ days)

---

## 🧱 Tech stack
Python · Pandas · SQLite · Streamlit · Plotly · Faker · ReportLab · APScheduler

---

## 📁 Project structure
```
TMS_Intelligence/
├── app.py                  # Streamlit entry point (landing page)
├── data/
│   ├── generate_data.py    # Simulated TMS data generator
│   └── transport.db        # SQLite DB (auto-generated on first run)
├── pages/
│   ├── 01_overview.py      ├── 04_incidents.py
│   ├── 02_routes.py        ├── 05_reports.py
│   ├── 03_vehicles.py      └── 06_alerts.py
├── utils/
│   ├── db.py               # DB connection & query helpers
│   ├── ui.py               # Shared branding, colours, sidebar filters
│   ├── anomaly.py          # Anomaly detection engine
│   ├── report_generator.py # PDF report generation
│   ├── email_alert.py      # SMTP email alerts
│   └── scheduler.py        # APScheduler background jobs
├── .streamlit/
│   ├── config.toml         # Theme
│   └── secrets.toml.example# Email config template
├── requirements.txt
└── README.md
```

---

## 🚀 Run locally
```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd TMS_Intelligence

# 2. Create a virtual environment & install dependencies
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. (Optional) generate the dataset — the app also does this automatically
python data/generate_data.py

# 4. Launch the dashboard
streamlit run app.py
```
The app opens at `http://localhost:8501`.

---

## ☁️ Deploy to Streamlit Community Cloud (free, public URL)

1. **Push to GitHub** — create a public repo and push this project.
   The SQLite database is git-ignored; the app **regenerates it automatically**
   on first load, so you don't need to commit `transport.db`.
2. Go to **[share.streamlit.io](https://share.streamlit.io)** and sign in with GitHub.
3. Click **"New app"** and select your repository and branch.
4. Set **Main file path** to `app.py`.
5. Click **Deploy**. Streamlit installs `requirements.txt` and builds the app.
6. You'll get a public URL like `https://your-app.streamlit.app` — add it to
   your resume and portfolio.

### (Optional) Enable email alerts
In the deployed app's **Settings → Secrets**, paste the keys from
`.streamlit/secrets.toml.example` (SMTP host, port, user, app-password,
from/to). The Anomaly Alerts page then sends live emails. Without this, the app
still runs fully — it just reports that email is not configured.

---

## 🎤 Demo / interview talking points
- *"It automatically flags route performance issues before a manager has to go looking for them."*
- *"Daily and weekly PDF reports auto-generate so the operations team always has a summary ready."*
- *"I simulated realistic TMS data because I understand how transportation data is structured."*
- *"The data layer is fully swappable — point `utils/db.py` at a real TMS API or CSV export and everything else works unchanged."*

> All data is simulated with Faker for demonstration purposes.
