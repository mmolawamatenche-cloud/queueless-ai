"""SQLite persistence for queue reports, plans, and demo metrics."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path(__file__).resolve().parent / "queueless.db"
MEMORY_DB_URI = "file:queueless_shared?mode=memory&cache=shared"
_SHARED_CONN = sqlite3.connect(MEMORY_DB_URI, uri=True, check_same_thread=False)
_SHARED_CONN.row_factory = sqlite3.Row


def _connect() -> sqlite3.Connection:
    return _SHARED_CONN


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS queue_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch_id TEXT NOT NULL,
                crowd_level TEXT NOT NULL,
                wait_minutes INTEGER,
                service_id TEXT,
                created_at TEXT NOT NULL,
                demo INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_query TEXT NOT NULL,
                service_id TEXT,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                useful INTEGER NOT NULL,
                comment TEXT,
                plan_id INTEGER,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS demo_bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                demo INTEGER DEFAULT 1,
                reference TEXT NOT NULL UNIQUE,
                service TEXT NOT NULL,
                branch TEXT NOT NULL,
                slot_time TEXT NOT NULL,
                status TEXT NOT NULL,
                disclaimer TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def add_queue_report(
    branch_id: str,
    crowd_level: str,
    wait_minutes: int | None = None,
    service_id: str | None = None,
) -> dict[str, Any]:
    created = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO queue_reports
                (branch_id, crowd_level, wait_minutes, service_id, created_at, demo)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (branch_id, crowd_level, wait_minutes, service_id, created),
        )
        report_id = cur.lastrowid
    return {
        "id": report_id,
        "branch_id": branch_id,
        "crowd_level": crowd_level,
        "wait_minutes": wait_minutes,
        "service_id": service_id,
        "created_at": created,
        "label": "User-reported (demo)",
    }


def list_queue_reports(limit: int = 50) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM queue_reports
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def recent_reports_for_branch(branch_id: str, hours: int = 4) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM queue_reports
            WHERE branch_id = ?
            ORDER BY datetime(created_at) DESC
            LIMIT 20
            """,
            (branch_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def save_plan(user_query: str, service_id: str | None, plan: dict[str, Any]) -> int:
    created = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO plans (user_query, service_id, plan_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_query, service_id, json.dumps(plan), created),
        )
        return int(cur.lastrowid)


def list_plans(limit: int = 20) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, user_query, service_id, plan_json, created_at
            FROM plans
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    results = []
    for r in rows:
        item = dict(r)
        item["plan"] = json.loads(item.pop("plan_json"))
        results.append(item)
    return results


def touch_session() -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (created_at) VALUES (?)",
            (datetime.now(timezone.utc).isoformat(),),
        )


def add_feedback(useful: bool, comment: str | None = None, plan_id: int | None = None) -> dict[str, Any]:
    created = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO feedback (useful, comment, plan_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (1 if useful else 0, comment, plan_id, created),
        )
        return {"id": cur.lastrowid, "useful": useful, "created_at": created}


def save_demo_booking(booking: dict[str, Any]) -> dict[str, Any]:
    init_db()
    created = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO demo_bookings
                (demo, reference, service, branch, slot_time, status, disclaimer, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1 if booking.get("demo") else 0,
                booking["reference"],
                booking["service"],
                booking["branch"],
                booking["slot_time"],
                booking["status"],
                booking["disclaimer"],
                created,
            ),
        )
        booking_id = cur.lastrowid
    return {
        "id": booking_id,
        "created_at": created,
        **booking,
    }


def list_demo_bookings(limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM demo_bookings
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def feedback_stats() -> dict[str, Any]:
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        useful = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE useful = 1"
        ).fetchone()[0]
    pct = round(100 * useful / total, 1) if total else None
    return {
        "feedback_count": total,
        "useful_count": useful,
        "useful_percent": pct,
    }


def dashboard_stats() -> dict[str, Any]:
    with get_db() as conn:
        report_count = conn.execute("SELECT COUNT(*) FROM queue_reports").fetchone()[0]
        plan_count = conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
        session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        avg_wait = conn.execute(
            "SELECT AVG(wait_minutes) FROM queue_reports WHERE wait_minutes IS NOT NULL"
        ).fetchone()[0]
        top_branches = conn.execute(
            """
            SELECT branch_id, COUNT(*) AS cnt
            FROM queue_reports
            GROUP BY branch_id
            ORDER BY cnt DESC
            LIMIT 5
            """
        ).fetchall()
        top_services = conn.execute(
            """
            SELECT service_id, COUNT(*) AS cnt
            FROM plans
            WHERE service_id IS NOT NULL
            GROUP BY service_id
            ORDER BY cnt DESC
            LIMIT 5
            """
        ).fetchall()
        crowd_now = conn.execute(
            """
            SELECT branch_id, crowd_level, wait_minutes, created_at
            FROM queue_reports
            WHERE id IN (
                SELECT MAX(id) FROM queue_reports GROUP BY branch_id
            )
            """
        ).fetchall()

    fb = feedback_stats()
    return {
        "queue_reports": report_count,
        "plans_created": plan_count,
        "active_sessions_approx": session_count,
        "average_reported_wait": round(avg_wait, 1) if avg_wait else None,
        "top_branches": [{"branch_id": r[0], "reports": r[1]} for r in top_branches],
        "top_services": [
            {"service_id": r[0], "requests": r[1]} for r in top_services
        ],
        "current_crowd_reports": [dict(r) for r in crowd_now],
        "traction": {
            "service_searches": plan_count,
            "queue_reports": report_count,
            "sessions": session_count,
            **fb,
        },
        "data_quality": {
            "mode": "Demo Mode",
            "label": "AI estimates based on historical/sample data + user reports",
            "live_government_api": False,
            "distinction": {
                "reported": "User-submitted crowd / wait observations",
                "predicted": "ML model estimate from patterns + reports",
                "demo_sample": "Historical CSV used to train the model — not live DHA",
            },
        },
    }
