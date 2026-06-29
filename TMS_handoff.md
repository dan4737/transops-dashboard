# Transportation Intelligence Dashboard — Project Handoff

## Project Overview
Build an automated transportation intelligence dashboard that simulates a Transport Management System (TMS), processes transportation data, and generates automated reports and visual dashboards. The goal is to demonstrate real-world supply chain analyst skills including data analysis, KPI tracking, anomaly detection, and automated reporting.

This project is being built as a portfolio piece for a Supply Chain Analyst / Transportation Coordinator role. It should look and feel like something a real logistics team would actually use.

---

## Tech Stack
- **Data Simulation**: Python + Faker library
- **Data Processing**: Python + Pandas
- **Database**: SQLite (single file, no setup required)
- **Dashboard**: Streamlit
- **Scheduling**: APScheduler (runs inside the Streamlit app)
- **Alerts**: SMTP email or Slack webhook when anomalies are detected
- **PDF Reports**: ReportLab or WeasyPrint
- **Deployment**: Streamlit Community Cloud (free, public link)

---

## Data Layer — Simulated TMS Dataset

Generate realistic fake transportation data that mirrors what a real TMS would output. The dataset should include the following fields:

### Deliveries Table
- delivery_id (unique)
- date (last 90 days)
- route_name (e.g. Windsor to Toronto, Brampton to Ottawa)
- vehicle_id
- driver_name
- scheduled_departure
- actual_departure
- scheduled_arrival
- actual_arrival
- delivery_status (On Time, Delayed, Cancelled, Failed)
- delay_reason (if delayed: Traffic, Weather, Vehicle Breakdown, Driver Issue, None)
- cargo_type (e.g. Steel Sheets, Aluminum Coils, Metal Rods)
- cargo_weight_kg
- distance_km
- fuel_used_litres
- incidents_reported (boolean)
- incident_description (if any)

### Vehicles Table
- vehicle_id
- vehicle_type (Truck, Van, Flatbed)
- plate_number
- capacity_kg
- current_status (Available, In Transit, Under Maintenance)
- last_maintenance_date
- total_trips_this_month

### Routes Table
- route_id
- route_name
- origin_city
- destination_city
- distance_km
- average_duration_hours
- assigned_vehicles (list)

Generate at least 500 rows of delivery data across the last 90 days. Make the data realistic — include some delays, some cancellations, seasonal patterns, and a few vehicle breakdown incidents. Routes should be Canadian cities: Windsor, Toronto, Brampton, Ottawa, Hamilton, London, Kitchener, Mississauga.

---

## Dashboard — Streamlit App

Build a multi-page Streamlit app with the following pages:

### Page 1 — Executive Overview
- Total deliveries this week vs last week (delta metric)
- On-time delivery rate % (large KPI card)
- Average delivery time across all routes
- Total incidents this week
- Vehicle utilization rate %
- A line chart showing daily delivery volume over the last 30 days
- A bar chart showing on-time vs delayed vs cancelled by week

### Page 2 — Route Performance
- Table showing all routes with their KPIs: avg delivery time, on-time rate, total deliveries, avg delay minutes
- Bar chart comparing on-time rate by route
- Highlight worst performing route in red
- Highlight best performing route in green
- Filter by date range, origin city, destination city

### Page 3 — Vehicle Management
- Table of all vehicles with current status, utilization %, total trips, last maintenance date
- Flag any vehicle that has not had maintenance in over 90 days in red
- Pie chart of vehicle status distribution (Available, In Transit, Maintenance)
- Filter by vehicle type

### Page 4 — Incident & Delay Analysis
- Total incidents by type (pie chart)
- Delay reasons breakdown (bar chart)
- Table of all incidents with date, route, vehicle, description
- Trend line showing delay frequency over time
- Filter by date range and delay reason

### Page 5 — Automated Reports
- Button that generates a PDF daily report for the current day
- Button that generates a PDF weekly report for the current week
- PDF should include: executive summary, KPI table, top issues, recommendations section
- Show a preview of the last generated report in the app
- Download button for the PDF

### Page 6 — Anomaly Alerts
- Table showing all triggered anomalies
- An anomaly is triggered when:
  - A route's on-time rate drops below 70% in the last 7 days
  - A vehicle has more than 3 incidents in 30 days
  - Delay rate spikes more than 20% compared to previous week
- Each anomaly shows: severity (High, Medium, Low), description, affected route or vehicle, date triggered
- A "Send Alert Email" button that fires an email notification for unresolved anomalies

---

## Automated Report Logic

### Daily Report (auto generates at 7am or on button click)
Include:
- Date
- Total deliveries scheduled vs completed
- On-time rate for the day
- Any delays and reasons
- Vehicles in use vs available
- Incidents reported
- Top performing route of the day
- Any open anomalies

### Weekly Report (auto generates Monday morning or on button click)
Include:
- Week summary
- KPI table (on-time rate, avg delivery time, vehicle utilization, incident count)
- Week over week comparison
- Route performance ranking
- Top 3 issues of the week
- Recommendations section (auto generated based on data patterns)
- Charts embedded in the PDF

---

## Anomaly Detection & Alert System

Build a simple anomaly detection engine that runs automatically:

```python
def check_anomalies(df):
    anomalies = []
    
    # Rule 1: Route on-time rate below 70% in last 7 days
    # Rule 2: Vehicle with 3+ incidents in 30 days  
    # Rule 3: Delay rate spike > 20% vs previous week
    # Rule 4: Vehicle overdue for maintenance (90+ days)
    
    return anomalies
```

When an anomaly is detected:
- Log it to an anomalies table in SQLite
- Display it on the Alerts page in the dashboard
- Optionally send an email notification using SMTP

---

## File Structure

```
transportation-dashboard/
│
├── app.py                  # Main Streamlit app entry point
├── data/
│   ├── generate_data.py    # Script to generate fake TMS data
│   └── transport.db        # SQLite database
├── pages/
│   ├── 01_overview.py
│   ├── 02_routes.py
│   ├── 03_vehicles.py
│   ├── 04_incidents.py
│   ├── 05_reports.py
│   └── 06_alerts.py
├── utils/
│   ├── db.py               # Database connection and query helpers
│   ├── anomaly.py          # Anomaly detection logic
│   ├── report_generator.py # PDF report generation
│   └── email_alert.py      # Email notification logic
├── assets/
│   └── logo.png            # Optional branding
├── requirements.txt
└── README.md
```

---

## Design & UI Requirements

- Use Streamlit's native dark or light theme
- Use st.metrics for all KPI cards at the top of each page
- Color code statuses consistently: green = on time, red = delayed/issue, yellow = warning
- Every page should have a date range filter in the sidebar
- The app should feel like a real internal logistics tool not a school project
- Add a sidebar with navigation and a company name "TransOps Dashboard" or similar
- Make sure all charts are labeled clearly with titles and axis labels

---

## Deployment Instructions

1. Push to GitHub repository
2. Go to share.streamlit.io
3. Connect GitHub repo
4. Set main file as app.py
5. Deploy — generates a public URL
6. Add the live URL to your resume and portfolio

---

## How to Present This Project

When showing this to a hiring manager or in an interview:

1. Open the live Streamlit link — show the executive dashboard first
2. Walk through the route performance page and explain how you would use it to identify underperforming routes
3. Show the anomaly alerts page and explain the business logic behind each rule
4. Generate a PDF report live during the demo
5. Explain the data simulation and how it mirrors a real TMS output
6. Mention it can be connected to a real TMS API by swapping the SQLite layer for a live data feed

---

## Key Talking Points for Interviews

- "I built a system that automatically flags route performance issues before a manager has to go looking for them"
- "The PDF reports auto-generate daily and weekly so the operations team always has a summary ready without manual work"
- "I simulated realistic TMS data because I understand how transportation data is structured from my supply chain management background"
- "This can be connected to any real TMS that has an API or CSV export — the data layer is fully swappable"

---

## Notes for Claude

- Build everything in one session if possible
- Start with generate_data.py first so there is data to work with before building the dashboard
- Make the fake data realistic — include weekday vs weekend patterns, seasonal delays, realistic Canadian city routes
- The Streamlit app should be fully functional and deployable with no errors
- Use plotly charts inside Streamlit for better interactivity than matplotlib
- Keep the code clean and well commented so it can be explained in an interview
- requirements.txt should include all dependencies so deployment works first try