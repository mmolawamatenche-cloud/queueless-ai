"""Round-robin rotation across similarly quiet, upcoming branch time slots."""
from __future__ import annotations

import csv
import math
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, TypedDict

SAST = timezone(timedelta(hours=2))
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ROTATION_DB = Path(__file__).resolve().parent.parent / "database" / "queueless.db"
SAFETY_MARGIN = timedelta(minutes=15)


class SlotPayload(TypedDict):
    date: str
    day: str
    start: str
    end: str
    start_iso: str
    wait_minutes: int
    wait_range: list[int]


class RotationInfo(TypedDict):
    position: int
    pool_size: int


class RotationRecommendation(TypedDict):
    slot: SlotPayload
    label: str
    recommended_text: str
    rotation: RotationInfo
    alternatives: list[SlotPayload]
    note: str


def now_sast() -> datetime:
    return datetime.now(SAST)


def _hour(value: str) -> float | None:
    if not value:
        return None
    hours, minutes = value.split(":")
    return int(hours) + int(minutes) / 60


def load_branch_hours(branch_id: str) -> dict[int, tuple[float, float]]:
    """Return weekday opening/closing hours for a branch in BRANCHE.csv."""
    with (DATA_DIR / "BRANCHE.csv").open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            if row["branch_id"] != branch_id:
                continue
            hours = {}
            for weekday, key in enumerate(
                ("mon", "tue", "wed", "thu", "fri", "sat")
            ):
                opening = _hour(row[f"open_{key}"])
                closing = _hour(row[f"close_{key}"])
                if opening is not None and closing is not None:
                    hours[weekday] = (opening, closing)
            return hours
    raise KeyError(f"Unknown branch_id: {branch_id}")


def load_holidays() -> set[date]:
    with (DATA_DIR / "sa_public_holidays.csv").open(
        encoding="utf-8", newline=""
    ) as file:
        return {
            date.fromisoformat(row["date"])
            for row in csv.DictReader(file)
        }


@dataclass(frozen=True)
class Slot:
    start: datetime
    end: datetime
    close: datetime
    wait: float
    wait_range: tuple[int, int]

    def to_dict(self) -> SlotPayload:
        return {
            "date": self.start.date().isoformat(),
            "day": self.start.strftime("%A"),
            "start": self.start.strftime("%H:%M"),
            "end": self.end.strftime("%H:%M"),
            "start_iso": self.start.isoformat(),
            "wait_minutes": round(self.wait),
            "wait_range": list(self.wait_range),
        }


def open_slots(
    branch_id: str,
    now: datetime,
    horizon_days: int = 7,
    lead_minutes: int = 60,
) -> list[tuple[datetime, datetime]]:
    """List hourly starts that are open, not on holidays, and still in the future."""
    hours = load_branch_hours(branch_id)
    holidays = load_holidays()
    slots = []
    for offset in range(horizon_days):
        current_date = (now + timedelta(days=offset)).date()
        opening_close = hours.get(current_date.weekday())
        if current_date in holidays or opening_close is None:
            continue

        opening, closing = opening_close
        close_at = datetime.combine(current_date, datetime.min.time(), tzinfo=SAST)
        close_at += timedelta(hours=closing)
        for hour in range(math.ceil(opening), math.ceil(closing)):
            start = datetime.combine(
                current_date, datetime.min.time(), tzinfo=SAST
            ) + timedelta(hours=hour)
            if start >= now + timedelta(minutes=lead_minutes):
                slots.append((start, close_at))
    return slots


def build_pool(
    scored: list[Slot],
    tolerance_minutes: int = 10,
    tolerance_pct: float = 0.25,
    max_size: int = 6,
    max_per_hour: int = 3,
    max_per_day: int = 2,
) -> list[Slot]:
    """Keep comparably quiet options distributed across days and hours."""
    best = min(slot.wait for slot in scored)
    limit = best + max(tolerance_minutes, best * tolerance_pct)
    near = sorted(
        (slot for slot in scored if slot.wait <= limit),
        key=lambda slot: (slot.wait, slot.start),
    )
    pool: list[Slot] = []
    seen: set[tuple[int, int]] = set()
    per_hour: dict[int, int] = {}
    per_day: dict[date, int] = {}

    for slot in near:
        hour = slot.start.hour
        day = slot.start.date()
        key = (slot.start.weekday(), hour)
        if (
            key in seen
            or per_hour.get(hour, 0) >= max_per_hour
            or per_day.get(day, 0) >= max_per_day
        ):
            continue
        pool.append(slot)
        seen.add(key)
        per_hour[hour] = per_hour.get(hour, 0) + 1
        per_day[day] = per_day.get(day, 0) + 1
        if len(pool) == max_size:
            break
    return sorted(pool, key=lambda slot: slot.start)


def next_rotation_index(
    branch_id: str, service_id: str, db_path: Path = ROTATION_DB
) -> int:
    """Atomically increment and return a persistent branch/service rotation counter."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    key = f"{branch_id}|{service_id}"
    with sqlite3.connect(db_path, timeout=5) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS slot_rotation (
                   key TEXT PRIMARY KEY,
                   counter INTEGER NOT NULL
               )"""
        )
        connection.execute(
            "INSERT OR IGNORE INTO slot_rotation (key, counter) VALUES (?, 0)",
            (key,),
        )
        row = connection.execute(
            "SELECT counter FROM slot_rotation WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            raise RuntimeError("Failed to read the slot rotation counter.")
        connection.execute(
            "UPDATE slot_rotation SET counter = counter + 1 WHERE key = ?", (key,)
        )
        return int(row[0])


def _day_label(slot_start: datetime, now: datetime) -> str:
    days_away = (slot_start.date() - now.date()).days
    if days_away == 0:
        return "today"
    if days_away == 1:
        return "tomorrow"
    if days_away < 7:
        return f"on {slot_start.strftime('%A')}"
    return f"next {slot_start.strftime('%A')}"


def _long_date(slot_start: datetime) -> str:
    return f"{slot_start.strftime('%A')}, {slot_start.day} {slot_start.strftime('%B %Y')}"


def recommend_slot(
    branch_id: str,
    predict_wait: Callable[[datetime], tuple[float, tuple[int, int]]],
    *,
    now: datetime | None = None,
    rotation_index: int = 0,
    horizon_days: int = 7,
    lead_minutes: int = 60,
) -> RotationRecommendation | None:
    """Rotate among upcoming, similarly quiet slots for a single branch."""
    now = now or now_sast()
    scored = []
    for start, close in open_slots(branch_id, now, horizon_days, lead_minutes):
        wait, estimate_range = predict_wait(start)
        if start + timedelta(minutes=wait) + SAFETY_MARGIN <= close:
            scored.append(
                Slot(
                    start=start,
                    end=min(start + timedelta(hours=1), close),
                    close=close,
                    wait=wait,
                    wait_range=estimate_range,
                )
            )
    if not scored:
        return None

    pool = build_pool(scored)
    position = rotation_index % len(pool)
    chosen = pool[position]
    low, high = chosen.wait_range
    return {
        "slot": chosen.to_dict(),
        "label": f"{_day_label(chosen.start, now)}, "
        f"{chosen.start.strftime('%H:%M')}-{chosen.end.strftime('%H:%M')}",
        "recommended_text": f"{_long_date(chosen.start)} "
        f"{chosen.start.strftime('%H:%M')}-{chosen.end.strftime('%H:%M')}",
        "rotation": {"position": position + 1, "pool_size": len(pool)},
        "alternatives": [slot.to_dict() for slot in pool if slot != chosen],
        "note": (
            f"Estimated wait {low}-{high} min. We rotate between {len(pool)} "
            f"similarly quiet times so no single slot gets crowded - this is "
            f"option {position + 1} of {len(pool)}."
        ),
    }


def plan_is_stale(slot_start_iso: str, now: datetime | None = None) -> bool:
    """Tell whether a saved recommendation's start time has passed."""
    now = now or now_sast()
    slot_start = datetime.fromisoformat(slot_start_iso)
    if slot_start.tzinfo is None:
        slot_start = slot_start.replace(tzinfo=SAST)
    return slot_start <= now
