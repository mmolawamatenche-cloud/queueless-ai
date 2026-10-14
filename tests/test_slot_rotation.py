from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from backend.ai import slot_rotation


SAST = timezone(timedelta(hours=2))


def test_rotation_returns_different_similarly_quiet_slots(monkeypatch):
    now = datetime(2026, 10, 14, 10, 0, tzinfo=SAST)
    slots = [
        (
            datetime(2026, 10, 15, 10, 0, tzinfo=SAST),
            datetime(2026, 10, 15, 15, 30, tzinfo=SAST),
        ),
        (
            datetime(2026, 10, 16, 11, 0, tzinfo=SAST),
            datetime(2026, 10, 16, 15, 30, tzinfo=SAST),
        ),
        (
            datetime(2026, 10, 19, 12, 0, tzinfo=SAST),
            datetime(2026, 10, 19, 15, 30, tzinfo=SAST),
        ),
    ]
    monkeypatch.setattr(slot_rotation, "open_slots", Mock(return_value=slots))
    predict_wait = Mock(return_value=(20, (15, 25)))

    first = slot_rotation.recommend_slot(
        "jhb_cbd", predict_wait, now=now, rotation_index=0
    )
    second = slot_rotation.recommend_slot(
        "jhb_cbd", predict_wait, now=now, rotation_index=1
    )

    assert first is not None
    assert second is not None
    assert first["slot"]["start_iso"] != second["slot"]["start_iso"]
    assert first["slot"]["wait_range"] == [15, 25]
    assert first["alternatives"]
    assert first["recommended_text"]
    assert "rotate between" in first["note"]


def test_slot_window_does_not_run_past_branch_closing(monkeypatch):
    now = datetime(2026, 10, 14, 14, 0, tzinfo=SAST)
    closing = datetime(2026, 10, 14, 15, 30, tzinfo=SAST)
    monkeypatch.setattr(
        slot_rotation, "open_slots", Mock(return_value=[(now + timedelta(hours=1), closing)])
    )

    recommendation = slot_rotation.recommend_slot(
        "jhb_cbd",
        Mock(return_value=(10, (8, 12))),
        now=now,
    )

    assert recommendation is not None
    assert recommendation["slot"]["start"] == "15:00"
    assert recommendation["slot"]["end"] == "15:30"


def test_rotation_counter_is_separate_per_branch_and_service(tmp_path):
    db_path = tmp_path / "rotation.db"

    assert slot_rotation.next_rotation_index("branch-a", "passport", db_path) == 0
    assert slot_rotation.next_rotation_index("branch-a", "passport", db_path) == 1
    assert slot_rotation.next_rotation_index("branch-a", "id", db_path) == 0
    assert slot_rotation.next_rotation_index("branch-b", "passport", db_path) == 0


def test_plan_is_stale_at_or_after_slot_start():
    start = datetime(2026, 10, 15, 10, 0, tzinfo=SAST)

    assert not slot_rotation.plan_is_stale(
        start.isoformat(), now=start - timedelta(minutes=1)
    )
    assert slot_rotation.plan_is_stale(start.isoformat(), now=start)
    assert slot_rotation.plan_is_stale(
        start.isoformat(), now=start + timedelta(minutes=1)
    )
