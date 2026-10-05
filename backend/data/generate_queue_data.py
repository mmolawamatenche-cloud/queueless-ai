"""Generate realistic sample historical queue data for demo mode."""
from __future__ import annotations

import csv
import random
from pathlib import Path

BRANCHES = [
    "jhb_cbd",
    "soweto",
    "randburg",
    "pta_cbd",
    "sandton",
]
SERVICES = [
    "passport_renewal",
    "passport_new",
    "id_application",
    "id_replacement",
    "birth_registration",
]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
HOURS = [8, 9, 10, 11, 12, 13, 14, 15]

# Base wait patterns (branch, hour) -> minutes
BASE = {
    "jhb_cbd": {8: 95, 9: 85, 10: 75, 11: 65, 12: 55, 13: 50, 14: 40, 15: 55},
    "soweto": {8: 70, 9: 60, 10: 50, 11: 45, 12: 40, 13: 35, 14: 30, 15: 40},
    "randburg": {8: 65, 9: 55, 10: 45, 11: 40, 12: 35, 13: 30, 14: 28, 15: 38},
    "pta_cbd": {8: 100, 9: 90, 10: 80, 11: 70, 12: 60, 13: 55, 14: 45, 15: 60},
    "sandton": {8: 55, 9: 50, 10: 42, 11: 38, 12: 32, 13: 28, 14: 25, 15: 35},
}
DAY_FACTOR = {
    "Monday": 1.25,
    "Tuesday": 1.05,
    "Wednesday": 0.95,
    "Thursday": 0.9,
    "Friday": 1.2,
}
SERVICE_FACTOR = {
    "passport_renewal": 1.0,
    "passport_new": 1.1,
    "id_application": 0.95,
    "id_replacement": 1.05,
    "birth_registration": 0.9,
}


def main() -> None:
    random.seed(42)
    out = Path(__file__).resolve().parent / "queue_data.csv"
    rows: list[dict] = []
    # ~8 weeks of sample observations
    for week in range(8):
        for day in DAYS:
            for branch in BRANCHES:
                for hour in HOURS:
                    for service in SERVICES:
                        if random.random() < 0.35:
                            continue
                        base = BASE[branch][hour]
                        wait = int(
                            base
                            * DAY_FACTOR[day]
                            * SERVICE_FACTOR[service]
                            * random.uniform(0.85, 1.15)
                        )
                        wait = max(10, min(180, wait))
                        crowd = (
                            "high"
                            if wait >= 80
                            else "medium"
                            if wait >= 45
                            else "low"
                        )
                        rows.append(
                            {
                                "branch_id": branch,
                                "day": day,
                                "hour": f"{hour:02d}:00",
                                "service_id": service,
                                "wait_minutes": wait,
                                "crowd_level": crowd,
                                "is_holiday": 0,
                                "month": ((week % 12) + 1),
                                "source": "historical_sample",
                            }
                        )

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "branch_id",
                "day",
                "hour",
                "service_id",
                "wait_minutes",
                "crowd_level",
                "is_holiday",
                "month",
                "source",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
