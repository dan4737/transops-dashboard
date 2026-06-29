"""
generate_data.py
================
Generates a realistic, simulated Transport Management System (TMS) dataset and
writes it into a single SQLite database (data/transport.db).

The script builds three core tables plus one empty table used later by the
anomaly engine:

    routes      - master list of lanes between Canadian cities
    vehicles    - the fleet (trucks, vans, flatbeds)
    deliveries  - 500+ shipment records across the last 90 days
    anomalies   - empty table; populated at runtime by the anomaly engine

The data is intentionally "messy but realistic": weekday/weekend volume
patterns, a configurable share of delays / cancellations / failures, a couple
of deliberately under-performing routes and accident-prone vehicles, and a few
vehicles that are overdue for maintenance. These patterns make the downstream
dashboard KPIs and anomaly rules light up with believable signals.

Run it directly:

    python data/generate_data.py
"""

from __future__ import annotations

import os
import random
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
from faker import Faker

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

# Deterministic output so the dashboard looks the same on every machine / deploy.
SEED = 42
random.seed(SEED)
fake = Faker("en_CA")
Faker.seed(SEED)

# Resolve paths relative to this file so the script works from any CWD.
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DATA_DIR, "transport.db")

# The dataset is anchored to "today" minus a 90-day window.
TODAY = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
WINDOW_DAYS = 90
START_DATE = TODAY - timedelta(days=WINDOW_DAYS)

NUM_DELIVERIES = 650          # comfortably above the 500-row minimum
NUM_VEHICLES = 22

# Canadian (Ontario) cities required by the brief.
CITIES = [
    "Windsor", "Toronto", "Brampton", "Ottawa",
    "Hamilton", "London", "Kitchener", "Mississauga",
]

CARGO_TYPES = ["Steel Sheets", "Aluminum Coils", "Metal Rods", "Steel Beams", "Copper Wire"]

VEHICLE_TYPES = ["Truck", "Van", "Flatbed"]

DELAY_REASONS = ["Traffic", "Weather", "Vehicle Breakdown", "Driver Issue"]

INCIDENT_TEMPLATES = {
    "Vehicle Breakdown": [
        "Engine overheating on highway, vehicle towed",
        "Flat tire en route, delayed roadside repair",
        "Transmission failure, load transferred to backup unit",
        "Brake warning light, pulled over for inspection",
    ],
    "Weather": [
        "Heavy snow squall reduced visibility, convoy slowed",
        "Black ice on Highway 401, precautionary stop",
        "Severe thunderstorm, sheltered until cleared",
    ],
    "Traffic": [
        "Multi-vehicle collision closed two lanes",
        "Construction detour added significant time",
    ],
    "Driver Issue": [
        "Driver hours-of-service limit reached, mandatory rest",
        "Driver illness, relief driver dispatched",
    ],
}


# --------------------------------------------------------------------------- #
# Route master data
# --------------------------------------------------------------------------- #

# Approximate real driving distances (km) between Ontario cities. Used to keep
# distance / duration / fuel numbers believable.
ROUTE_DEFS = [
    ("Windsor", "Toronto", 375),
    ("Windsor", "London", 190),
    ("Brampton", "Ottawa", 450),
    ("Toronto", "Ottawa", 450),
    ("Hamilton", "Toronto", 70),
    ("London", "Kitchener", 110),
    ("Mississauga", "Ottawa", 420),
    ("Kitchener", "Toronto", 110),
    ("London", "Toronto", 190),
    ("Hamilton", "Ottawa", 500),
    ("Windsor", "Hamilton", 300),
    ("Brampton", "Hamilton", 55),
    ("Mississauga", "London", 160),
    ("Kitchener", "Ottawa", 530),
]

AVG_SPEED_KMH = 80  # used to derive a nominal duration from distance


def build_routes() -> pd.DataFrame:
    """Create the routes master table."""
    rows = []
    for i, (origin, dest, dist) in enumerate(ROUTE_DEFS, start=1):
        rows.append(
            {
                "route_id": f"R{i:03d}",
                "route_name": f"{origin} to {dest}",
                "origin_city": origin,
                "destination_city": dest,
                "distance_km": dist,
                "average_duration_hours": round(dist / AVG_SPEED_KMH, 2),
                "assigned_vehicles": "",  # filled in after vehicles exist
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Vehicle fleet
# --------------------------------------------------------------------------- #

def build_vehicles() -> pd.DataFrame:
    """Create the vehicle fleet table."""
    rows = []
    for i in range(1, NUM_VEHICLES + 1):
        vtype = random.choices(VEHICLE_TYPES, weights=[0.55, 0.25, 0.20])[0]

        # Capacity depends on vehicle type.
        if vtype == "Truck":
            capacity = random.choice([18000, 20000, 24000])
        elif vtype == "Flatbed":
            capacity = random.choice([22000, 26000, 30000])
        else:  # Van
            capacity = random.choice([3500, 4000, 5000])

        # Most vehicles serviced recently; a deliberate few are overdue (>90d)
        # so the maintenance anomaly rule has something to find.
        if i in (3, 14):
            days_since_service = random.randint(95, 140)   # overdue
        else:
            days_since_service = random.randint(5, 85)     # within policy
        last_maint = (TODAY - timedelta(days=days_since_service)).date().isoformat()

        rows.append(
            {
                "vehicle_id": f"V{i:03d}",
                "vehicle_type": vtype,
                "plate_number": fake.bothify(text="???-####").upper(),
                "capacity_kg": capacity,
                "current_status": random.choices(
                    ["Available", "In Transit", "Under Maintenance"],
                    weights=[0.5, 0.4, 0.1],
                )[0],
                "last_maintenance_date": last_maint,
                "total_trips_this_month": 0,  # computed from deliveries later
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Deliveries (the fact table)
# --------------------------------------------------------------------------- #

def _status_for(route_name: str, day: datetime, problem_routes: set) -> str:
    """
    Pick a delivery status with realistic probabilities.

    Problem routes get a much higher delay rate so the route-performance and
    anomaly pages surface a clear "worst route". A mild recency bias nudges the
    most recent week worse, which feeds the week-over-week spike rule.
    """
    base = {"On Time": 0.78, "Delayed": 0.14, "Cancelled": 0.05, "Failed": 0.03}

    if route_name in problem_routes:
        base = {"On Time": 0.50, "Delayed": 0.34, "Cancelled": 0.09, "Failed": 0.07}

    # Recency bias: deliveries in the last 7 days are a bit more troubled,
    # simulating an emerging operational issue.
    if (TODAY - day).days <= 7:
        base = {
            "On Time": base["On Time"] - 0.08,
            "Delayed": base["Delayed"] + 0.06,
            "Cancelled": base["Cancelled"] + 0.01,
            "Failed": base["Failed"] + 0.01,
        }

    statuses = list(base.keys())
    weights = [max(w, 0.01) for w in base.values()]
    return random.choices(statuses, weights=weights)[0]


def build_deliveries(routes: pd.DataFrame, vehicles: pd.DataFrame) -> pd.DataFrame:
    """Create the deliveries fact table."""
    route_lookup = routes.set_index("route_name").to_dict("index")
    vehicle_ids = vehicles["vehicle_id"].tolist()

    # Deliberately under-performing routes (drive worst-route + anomaly signals).
    problem_routes = {"Kitchener to Ottawa", "Hamilton to Ottawa"}

    # One accident-prone vehicle to satisfy the "3+ incidents in 30 days" rule.
    accident_prone = "V007"

    # Pre-build a pool of dates weighted by weekday (fewer on weekends).
    date_pool = []
    for d in range(WINDOW_DAYS):
        day = START_DATE + timedelta(days=d)
        weight = 2 if day.weekday() < 5 else 1  # Mon-Fri busier than Sat/Sun
        date_pool.extend([day] * weight)

    rows = []
    for n in range(1, NUM_DELIVERIES + 1):
        route_name = random.choice(list(route_lookup.keys()))
        route = route_lookup[route_name]
        day = random.choice(date_pool)

        # Bias the accident-prone vehicle toward recent dates so its incidents
        # cluster inside the 30-day anomaly window.
        if random.random() < 0.06:
            vehicle_id = accident_prone
            day = TODAY - timedelta(days=random.randint(0, 28))
        else:
            vehicle_id = random.choice(vehicle_ids)

        status = _status_for(route_name, day, problem_routes)

        # --- Scheduled times -------------------------------------------------
        dep_hour = random.randint(5, 18)
        dep_minute = random.choice([0, 15, 30, 45])
        scheduled_departure = day.replace(hour=dep_hour, minute=dep_minute)
        duration_h = route["average_duration_hours"]
        scheduled_arrival = scheduled_departure + timedelta(hours=duration_h)

        # --- Actual times + delay logic -------------------------------------
        delay_reason = "None"
        incident_reported = False
        incident_description = ""

        if status == "Cancelled":
            # Cancelled trips never actually run.
            actual_departure = None
            actual_arrival = None
        else:
            dep_jitter = random.randint(-5, 10)  # usually leave roughly on time
            actual_departure = scheduled_departure + timedelta(minutes=dep_jitter)

            if status == "On Time":
                arr_jitter = random.randint(-15, 10)
                actual_arrival = scheduled_arrival + timedelta(minutes=arr_jitter)
            else:  # Delayed or Failed
                delay_reason = random.choices(
                    DELAY_REASONS, weights=[0.4, 0.25, 0.2, 0.15]
                )[0]
                delay_minutes = random.randint(35, 240)
                actual_arrival = scheduled_arrival + timedelta(minutes=delay_minutes)

                # Some delays escalate into a logged incident.
                breakdown = delay_reason in ("Vehicle Breakdown", "Weather")
                force_incident = vehicle_id == accident_prone and random.random() < 0.7
                if breakdown or force_incident or random.random() < 0.15:
                    incident_reported = True
                    templates = INCIDENT_TEMPLATES.get(
                        delay_reason, INCIDENT_TEMPLATES["Traffic"]
                    )
                    incident_description = random.choice(templates)

            if status == "Failed":
                # A failed delivery never reaches destination.
                actual_arrival = None

        # --- Cargo, distance, fuel ------------------------------------------
        cargo_type = random.choice(CARGO_TYPES)
        cargo_weight = random.randint(1500, 18000)
        distance_km = route["distance_km"]
        # Fuel scales with distance and load; heavier loads burn more per km.
        fuel_rate = 0.30 + (cargo_weight / 18000) * 0.18 + random.uniform(-0.02, 0.02)
        fuel_used = round(distance_km * fuel_rate, 1)

        rows.append(
            {
                "delivery_id": f"D{n:05d}",
                "date": day.date().isoformat(),
                "route_name": route_name,
                "vehicle_id": vehicle_id,
                "driver_name": fake.name(),
                "scheduled_departure": scheduled_departure.isoformat(sep=" "),
                "actual_departure": actual_departure.isoformat(sep=" ") if actual_departure else None,
                "scheduled_arrival": scheduled_arrival.isoformat(sep=" "),
                "actual_arrival": actual_arrival.isoformat(sep=" ") if actual_arrival else None,
                "delivery_status": status,
                "delay_reason": delay_reason,
                "cargo_type": cargo_type,
                "cargo_weight_kg": cargo_weight,
                "distance_km": distance_km,
                "fuel_used_litres": fuel_used,
                "incidents_reported": int(incident_reported),
                "incident_description": incident_description,
            }
        )

    df = pd.DataFrame(rows)
    return df.sort_values("date").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Post-processing: link tables together
# --------------------------------------------------------------------------- #

def finalize_relationships(
    routes: pd.DataFrame, vehicles: pd.DataFrame, deliveries: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Backfill assigned_vehicles on routes and trips-this-month on vehicles."""
    # assigned_vehicles: distinct vehicles seen on each route.
    assigned = (
        deliveries.groupby("route_name")["vehicle_id"]
        .apply(lambda s: ", ".join(sorted(set(s))[:6]))
        .to_dict()
    )
    routes = routes.copy()
    routes["assigned_vehicles"] = routes["route_name"].map(assigned).fillna("")

    # total_trips_this_month: deliveries in the current calendar month.
    month_start = TODAY.replace(day=1).date().isoformat()
    this_month = deliveries[deliveries["date"] >= month_start]
    trips = this_month.groupby("vehicle_id")["delivery_id"].count().to_dict()
    vehicles = vehicles.copy()
    vehicles["total_trips_this_month"] = (
        vehicles["vehicle_id"].map(trips).fillna(0).astype(int)
    )
    return routes, vehicles


# --------------------------------------------------------------------------- #
# Write to SQLite
# --------------------------------------------------------------------------- #

def write_database(routes, vehicles, deliveries) -> None:
    """Persist all tables to SQLite, replacing any existing data."""
    conn = sqlite3.connect(DB_PATH)
    try:
        routes.to_sql("routes", conn, if_exists="replace", index=False)
        vehicles.to_sql("vehicles", conn, if_exists="replace", index=False)
        deliveries.to_sql("deliveries", conn, if_exists="replace", index=False)

        # Anomalies table: created empty here; the anomaly engine fills it later.
        conn.execute("DROP TABLE IF EXISTS anomalies")
        conn.execute(
            """
            CREATE TABLE anomalies (
                anomaly_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                rule            TEXT,
                severity        TEXT,
                description     TEXT,
                entity_type     TEXT,
                affected_entity TEXT,
                metric_value    REAL,
                date_triggered  TEXT,
                resolved        INTEGER DEFAULT 0
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    print("Generating simulated TMS data...")
    routes = build_routes()
    vehicles = build_vehicles()
    deliveries = build_deliveries(routes, vehicles)
    routes, vehicles = finalize_relationships(routes, vehicles, deliveries)

    write_database(routes, vehicles, deliveries)

    # Console summary so a human running the script gets immediate feedback.
    status_counts = deliveries["delivery_status"].value_counts().to_dict()
    on_time_rate = 100 * status_counts.get("On Time", 0) / len(deliveries)
    print(f"  Database written to: {DB_PATH}")
    print(f"  Routes:     {len(routes)}")
    print(f"  Vehicles:   {len(vehicles)}")
    print(f"  Deliveries: {len(deliveries)} "
          f"({START_DATE.date()} -> {TODAY.date()})")
    print(f"  Status mix: {status_counts}")
    print(f"  On-time rate: {on_time_rate:.1f}%")
    print(f"  Incidents logged: {int(deliveries['incidents_reported'].sum())}")
    print("Done.")


if __name__ == "__main__":
    main()
