"""Tests for comparing wait estimates across service branches."""
import pandas as pd
import pytest
from fastapi import HTTPException

from backend import main


class FakePredictor:
    def __init__(self):
        self.called_branches = []

    def predict(self, **kwargs):
        self.called_branches.append(kwargs["branch_id"])
        wait = {"branch_a": 42, "branch_b": 24}[kwargs["branch_id"]]
        return {
            "predicted_wait_minutes": wait,
            "wait_range_low": wait - 5,
            "wait_range_high": wait + 5,
            "confidence": 0.8,
        }

    @staticmethod
    def to_dict(result):
        return result


def test_compare_queues_ranks_only_branches_offering_service(monkeypatch):
    fake_predictor = FakePredictor()
    monkeypatch.setattr(main, "predictor", fake_predictor)
    monkeypatch.setattr(
        main.engine,
        "branches",
        pd.DataFrame(
            [
                {
                    "branch_id": "branch_a",
                    "branch_name": "Alpha",
                    "city": "City A",
                    "services_offered": "passport_renewal|id_replacement",
                },
                {
                    "branch_id": "branch_b",
                    "branch_name": "Beta",
                    "city": "City B",
                    "services_offered": "passport_renewal",
                },
                {
                    "branch_id": "branch_c",
                    "branch_name": "Gamma",
                    "city": "City C",
                    "services_offered": "id_replacement",
                },
            ]
        ),
    )
    monkeypatch.setattr(main.db, "recent_reports_for_branch", lambda branch_id: [])

    result = main.compare_queues(
        main.QueueComparisonRequest(
            service_id="passport_renewal",
            day="Wednesday",
            hour=10,
        )
    )

    assert [item["branch_id"] for item in result["comparisons"]] == [
        "branch_b",
        "branch_a",
    ]
    assert fake_predictor.called_branches == ["branch_a", "branch_b"]
    assert result["label"].startswith("AI estimates")


def test_compare_queues_rejects_weekends():
    with pytest.raises(HTTPException, match="day must be a weekday"):
        main.compare_queues(
            main.QueueComparisonRequest(
                service_id="passport_renewal",
                day="Sunday",
                hour=10,
            )
        )


def test_compare_queues_returns_not_found_without_matching_branches(monkeypatch):
    monkeypatch.setattr(
        main.engine,
        "branches",
        pd.DataFrame(
            [
                {
                    "branch_id": "branch_a",
                    "branch_name": "Alpha",
                    "city": "City A",
                    "services_offered": "id_replacement",
                }
            ]
        ),
    )

    with pytest.raises(HTTPException) as exc:
        main.compare_queues(
            main.QueueComparisonRequest(
                service_id="passport_renewal",
                day="Wednesday",
                hour=10,
            )
        )

    assert exc.value.status_code == 404
