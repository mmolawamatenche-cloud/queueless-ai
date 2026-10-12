"""Generate realistic sample historical queue data for demo mode."""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent

BRANCHES = [
    "jhb_cbd",
    "soweto",
    "randburg",
    "pta_cbd",
    "sandton",
    "mahikeng",
    "brits",
    "marabastad_pta",
    "ct_refugee_goodwood",
    "ct_refugee_reception",
    "jhb_standardbank",
    "ct_sassa_bellville",
    "ct_sassa_wynberg",
    "ct_sassa_citycentre",
    "dbn_sassa",
    "polokwane_sassa",
    "bfn_sassa",
    "ct_sars",
    "dbn_sars",
    "ct_labour",
    "dbn_labour",
    "ct_licensing_ottery",
    "ct_licensing_gallowshill",
    "pe_municipal",
    "kimberley_saps",
]

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
HOURS = [8, 9, 10, 11, 12, 13, 14, 15]

# Base wait patterns (branch, hour) -> minutes
BASE = {
    "jhb_cbd": {8: 95, 9: 85, 10: 75, 11: 65, 12: 55, 13: 50, 14: 40, 15: 55},
    "soweto": {8: 70, 9: 60, 10: 50, 11: 45, 12: 40, 13: 35, 14: 30, 15: 40},
    "randburg": {8: 65, 9: 55, 10: 45, 11: 40, 12: 35, 13: 30, 14: 28, 15: 38},
    "pta_cbd": {8: 100, 9: 90, 10: 80, 11: 70, 12: 60, 13: 55, 14: 45, 15: 60},
    "sandton": {8: 55, 9: 50, 10: 42, 11: 38, 12: 32, 13: 28, 14: 25, 15: 35},
    "mahikeng": {8: 60, 9: 55, 10: 48, 11: 42, 12: 38, 13: 32, 14: 30, 15: 36},
    "brits": {8: 52, 9: 48, 10: 41, 11: 36, 12: 32, 13: 29, 14: 25, 15: 34},
    "marabastad_pta": {8: 115, 9: 100, 10: 90, 11: 80, 12: 70, 13: 62, 14: 58, 15: 66},
    "ct_refugee_goodwood": {8: 75, 9: 68, 10: 62, 11: 57, 12: 54, 13: 48, 14: 40, 15: 52},
    "ct_refugee_reception": {8: 85, 9: 78, 10: 72, 11: 66, 12: 62, 13: 58, 14: 50, 15: 60},
    "jhb_standardbank": {8: 45, 9: 40, 10: 35, 11: 30, 12: 28, 13: 25, 14: 22, 15: 28},
    "ct_sassa_bellville": {8: 110, 9: 96, 10: 90, 11: 80, 12: 72, 13: 68, 14: 60, 15: 70},
    "ct_sassa_wynberg": {8: 95, 9: 88, 10: 82, 11: 72, 12: 66, 13: 60, 14: 55, 15: 62},
    "ct_sassa_citycentre": {8: 100, 9: 92, 10: 86, 11: 78, 12: 70, 13: 64, 14: 58, 15: 66},
    "dbn_sassa": {8: 92, 9: 85, 10: 82, 11: 74, 12: 68, 13: 62, 14: 56, 15: 64},
    "polokwane_sassa": {8: 88, 9: 80, 10: 74, 11: 70, 12: 64, 13: 58, 14: 52, 15: 60},
    "bfn_sassa": {8: 86, 9: 78, 10: 72, 11: 68, 12: 62, 13: 56, 14: 50, 15: 58},
    "ct_sars": {8: 60, 9: 55, 10: 52, 11: 46, 12: 40, 13: 38, 14: 36, 15: 42},
    "dbn_sars": {8: 58, 9: 50, 10: 46, 11: 42, 12: 38, 13: 35, 14: 32, 15: 40},
    "ct_labour": {8: 72, 9: 66, 10: 62, 11: 58, 12: 52, 13: 48, 14: 44, 15: 52},
    "dbn_labour": {8: 70, 9: 66, 10: 60, 11: 54, 12: 50, 13: 46, 14: 42, 15: 50},
    "ct_licensing_ottery": {8: 75, 9: 68, 10: 62, 11: 54, 12: 44, 13: 38, 14: 34, 15: 42},
    "ct_licensing_gallowshill": {8: 88, 9: 82, 10: 76, 11: 68, 12: 62, 13: 58, 14: 54, 15: 60},
    "pe_municipal": {8: 48, 9: 45, 10: 40, 11: 38, 12: 35, 13: 30, 14: 28, 15: 36},
    "kimberley_saps": {8: 52, 9: 48, 10: 43, 11: 40, 12: 36, 13: 32, 14: 28, 15: 34},
}
DAY_FACTOR = {
    "Monday": 1.25,
    "Tuesday": 1.1,
    "Wednesday": 1.0,
    "Thursday": 0.92,
    "Friday": 1.18,
    "Saturday": 0.72,
    "Sunday": 0.55,
}


def _service_ids() -> list[str]:
    path = DATA_DIR / "services.csv"
    if not path.exists():
        return [
            "id_application",
            "id_replacement",
            "passport_new",
            "passport_renewal",
            "birth_registration",
            "marriage_certificate",
            "death_certificate",
            "visa_application",
            "refugee_asylum",
            "amendment",
            "grant_application",
            "grant_query",
            "grant_appeal",
            "tax_registration",
            "efiling_support",
            "tax_query",
            "uif_claim",
            "uif_query",
            "domestic_worker_registration",
            "drivers_license_renewal",
            "drivers_license_new",
            "learners_license",
            "vehicle_registration",
            "utility_account",
            "indigent_registration",
            "municipal_query",
            "police_clearance",
            "affidavit",
            "outpatient_queue",
        ]
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [row["service_id"] for row in reader if row.get("service_id")]


def _branch_ids() -> list[str]:
    path = DATA_DIR / "BRANCHE.csv"
    if not path.exists():
        return BRANCHES
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [str(row["branch_id"]) for row in reader if row.get("branch_id")]


def _branch_services() -> dict[str, set[str]]:
    branch_ids = _branch_ids()
    service_ids = set(_service_ids())
    services_by_branch: dict[str, set[str]] = {branch_id: set() for branch_id in branch_ids}
    path = DATA_DIR / "BRANCHE.csv"
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                branch_id = str(row["branch_id"])
                offers = [item.strip() for item in str(row.get("services_offered", "")).split("|") if item.strip()]
                services_by_branch.setdefault(branch_id, set()).update(item for item in offers if item in service_ids)
    return services_by_branch


def _load_holidays() -> dict[date, str]:
    path = DATA_DIR / "sa_public_holidays.csv"
    holidays: dict[date, str] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            holiday_date = date.fromisoformat(row["date"])
            if holiday_date.strftime("%A") != row["day"]:
                raise ValueError(f"Holiday weekday does not match date: {row['date']}")
            if holiday_date.year != int(row["year"]):
                raise ValueError(f"Holiday year does not match date: {row['date']}")
            holidays[holiday_date] = row["holiday_name"]
    return holidays


def main() -> None:
    random.seed(42)
    out = DATA_DIR / "queue_data.csv"
    branches = _branch_ids()
    services = _service_ids()
    branch_services = _branch_services()
    holidays = _load_holidays()
    rows: list[dict[str, object]] = []

    start = date(2025, 1, 1)
    end = date(2025, 12, 31)
    current = start
    while current <= end:
        day_name = current.strftime("%A")
        for branch_id in branches:
            branch_base = BASE.get(branch_id, {8: 50, 9: 46, 10: 42, 11: 38, 12: 34, 13: 30, 14: 28, 15: 36})
            offered = branch_services.get(branch_id, set())
            for hour in HOURS:
                for service_id in services:
                    if service_id not in offered:
                        continue
                    if random.random() < 0.2:
                        continue
                    hour_modifier = 1.0 + (hour - 8) * 0.04
                    service_factor = {
                        "passport_renewal": 1.12,
                        "passport_new": 1.18,
                        "id_application": 1.0,
                        "id_replacement": 1.08,
                        "birth_registration": 0.94,
                        "marriage_certificate": 0.9,
                        "death_certificate": 0.98,
                        "visa_application": 1.06,
                        "refugee_asylum": 1.14,
                        "amendment": 0.88,
                        "grant_application": 1.24,
                        "grant_query": 1.12,
                        "grant_appeal": 1.2,
                        "tax_registration": 0.96,
                        "efiling_support": 0.9,
                        "tax_query": 0.92,
                        "uif_claim": 1.1,
                        "uif_query": 1.0,
                        "domestic_worker_registration": 0.88,
                        "drivers_license_renewal": 1.02,
                        "drivers_license_new": 1.08,
                        "learners_license": 0.96,
                        "vehicle_registration": 0.94,
                        "utility_account": 0.86,
                        "indigent_registration": 0.9,
                        "municipal_query": 0.82,
                        "police_clearance": 0.94,
                        "affidavit": 0.86,
                        "outpatient_queue": 0.84,
                    }.get(service_id, 1.0)
                    wait = int(
                        branch_base.get(hour, 40)
                        * DAY_FACTOR.get(day_name, 1.0)
                        * service_factor
                        * hour_modifier
                        * random.uniform(0.85, 1.15)
                    )
                    wait = max(10, min(180, wait))
                    crowd = "high" if wait >= 80 else "medium" if wait >= 45 else "low"
                    rows.append(
                        {
                            "branch_id": branch_id,
                            "date": current.isoformat(),
                            "day": day_name,
                            "hour": f"{hour:02d}:00",
                            "service_id": service_id,
                            "wait_minutes": wait,
                            "crowd_level": crowd,
                            "is_holiday": int(current in holidays),
                            "holiday_name": holidays.get(current, ""),
                            "day_of_month": current.day,
                            "month": current.month,
                            "year": current.year,
                            "source": "historical_sample",
                        }
                    )
        current += timedelta(days=1)

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "branch_id",
                "date",
                "day",
                "hour",
                "service_id",
                "wait_minutes",
                "crowd_level",
                "is_holiday",
                "holiday_name",
                "day_of_month",
                "month",
                "year",
                "source",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
