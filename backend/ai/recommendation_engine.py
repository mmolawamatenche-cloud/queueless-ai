"""AI recommendation engine — best branch, time, documents, and explanation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from backend.ai.queue_predictor import PredictionResult, QueuePredictor
from backend.ai.service_classifier import ServiceIntent
from backend.ai.slot_rotation import (
    RotationInfo,
    SlotPayload,
    load_holidays,
    next_rotation_index,
    recommend_slot,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

CITY_COORDS = {
    "johannesburg": (-26.2041, 28.0473),
    "jhb": (-26.2041, 28.0473),
    "soweto": (-26.2678, 27.8585),
    "randburg": (-26.0939, 28.0063),
    "pretoria": (-25.7461, 28.1881),
    "pta": (-25.7461, 28.1881),
    "sandton": (-26.1076, 28.0567),
    "mbombela": (-25.46987, 30.97857),
    "nelspruit": (-25.46987, 30.97857),
    "gauteng": (-26.0, 28.0),
}


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    import math

    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 6371 * 2 * math.asin(math.sqrt(h))


@dataclass
class DocumentItem:
    code: str
    name: str
    required: bool
    status: str  # have | missing | optional
    notes: str


@dataclass
class VisitPlan:
    service_id: str
    service_name: str
    category: str
    branch_id: str
    branch_name: str
    city: str
    address: str
    crowd_level: str
    crowd_label: str
    estimated_wait_low: int
    estimated_wait_high: int
    predicted_wait: int
    recommended_day: str
    recommended_date: str
    recommended_time: str
    recommended_text: str
    slot: SlotPayload
    rotation: RotationInfo
    rotation_note: str
    prediction_confidence: float
    documents: list[dict[str, Any]]
    missing_documents: list[str]
    reason: str
    ai_recommendation: str
    data_labels: dict[str, str]
    prediction_detail: dict[str, Any]
    evidence: dict[str, Any]
    disclaimer: str
    alternatives: list[dict[str, Any]]
    analysing_steps: list[dict[str, str]]


class RecommendationEngine:
    def __init__(self, predictor: QueuePredictor | None = None) -> None:
        self.branches = pd.read_csv(DATA_DIR / "BRANCHE.csv")
        self.documents = pd.read_csv(DATA_DIR / "documents.csv")
        self.predictor = predictor or QueuePredictor()

    def documents_for_service(
        self, service_id: str, user_has: list[str] | None = None
    ) -> list[DocumentItem]:
        user_has = {h.lower() for h in (user_has or [])}
        rows = self.documents[self.documents["service_id"] == service_id]
        items: list[DocumentItem] = []
        for _, row in rows.iterrows():
            code = str(row["document_code"])
            required = str(row["required"]).lower() == "true"
            # In MVP we mark appointment as commonly missing for demo impact
            if code in user_has or code.replace("_", " ") in user_has:
                status = "have"
            elif code == "appointment" and required:
                status = "missing"
            elif not required:
                status = "optional"
            else:
                status = "have" if code in ("sa_id", "payment") else "missing"
            # Demo defaults: assume ID + payment present; others need attention
            if status == "missing" and code in ("sa_id", "payment", "application"):
                status = "have"
            if code == "appointment" and required:
                status = "missing"
            items.append(
                DocumentItem(
                    code=code,
                    name=str(row["document_name"]),
                    required=required,
                    status=status,
                    notes=str(row.get("notes", "")),
                )
            )
        return items

    def _resolve_location(
        self, location: str | None, lat: float | None, lon: float | None
    ) -> tuple[float, float]:
        if lat is not None and lon is not None:
            return (lat, lon)
        if location:
            key = location.strip().lower()
            for name, coords in CITY_COORDS.items():
                if name in key:
                    return coords
        return CITY_COORDS["johannesburg"]

    def _day_keys(self, dt: datetime) -> tuple[str, str]:
        return dt.strftime("%A"), "open_" + dt.strftime("%a").lower()

    def _is_open(self, branch: pd.Series, dt: datetime) -> bool:
        day = dt.strftime("%a").lower()
        open_col = f"open_{day}"
        close_col = f"close_{day}"
        if open_col not in branch or pd.isna(branch[open_col]) or branch[open_col] == "":
            return False
        return True

    def _crowd_from_wait(self, wait: int) -> tuple[str, str]:
        if wait >= 80:
            return "high", "🔴 High / Very busy"
        if wait >= 45:
            return "medium", "🟡 Moderate"
        return "low", "🟢 Low"

    def build_plan(
        self,
        intent: ServiceIntent,
        location: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        user_documents: list[str] | None = None,
        recent_reports_by_branch: dict[str, list[dict[str, Any]]] | None = None,
    ) -> VisitPlan | None:
        if not intent.service_id:
            return None

        origin = self._resolve_location(location, lat, lon)
        recent_reports_by_branch = recent_reports_by_branch or {}

        # Candidate branches offering the service
        candidates = []
        for _, branch in self.branches.iterrows():
            offered = str(branch["services_offered"]).split("|")
            if intent.service_id not in offered:
                continue
            coords = (float(branch["latitude"]), float(branch["longitude"]))
            distance = _haversine_km(origin, coords)
            candidates.append((branch, distance))

        if not candidates:
            return None

        # Score upcoming weekday slots in the user's local South African time.
        now = datetime.now(ZoneInfo("Africa/Johannesburg"))
        horizon_days = 3 if intent.urgency == "high" else 7
        holidays = load_holidays()
        scored: list[dict[str, Any]] = []

        for branch, distance in candidates:
            for day_offset in range(horizon_days):
                dt = now + timedelta(days=day_offset)
                if dt.weekday() >= 5:  # skip weekend (branches closed in sample)
                    continue
                if dt.date() in holidays:
                    continue
                if not self._is_open(branch, dt):
                    continue
                day_name = dt.strftime("%A")
                for hour in (8, 10, 11, 14, 15):
                    if dt.date() == now.date() and hour <= now.hour:
                        continue
                    reports = recent_reports_by_branch.get(str(branch["branch_id"]), [])
                    pred = self.predictor.predict(
                        branch_id=str(branch["branch_id"]),
                        day=day_name,
                        hour=hour,
                        service_id=intent.service_id,
                        month=dt.month,
                        recent_reports=reports if day_offset == 0 else None,
                    )
                    # Prefer lower wait, closer branch, mid-afternoon historically quieter
                    score = (
                        pred.predicted_wait_minutes
                        + distance * 1.5
                        - (8 if hour in (14, 15) else 0)
                        + (12 if day_name == "Monday" else 0)
                    )
                    scored.append(
                        {
                            "branch": branch,
                            "distance": distance,
                            "day_name": day_name,
                            "date": dt.strftime("%Y-%m-%d"),
                            "hour": hour,
                            "pred": pred,
                            "score": score,
                        }
                    )

        scored.sort(key=lambda x: x["score"])
        if not scored:
            return None
        best = scored[0]
        branch = best["branch"]
        branch_id = str(branch["branch_id"])
        prediction_by_slot: dict[datetime, PredictionResult] = {}

        def predict_slot(slot_start: datetime) -> tuple[float, tuple[int, int]]:
            reports = recent_reports_by_branch.get(branch_id, [])
            prediction = self.predictor.predict(
                branch_id=branch_id,
                day=slot_start.strftime("%A"),
                hour=slot_start.hour,
                service_id=intent.service_id,
                month=slot_start.month,
                recent_reports=reports if slot_start.date() == now.date() else None,
            )
            prediction_by_slot[slot_start] = prediction
            return (
                prediction.predicted_wait_minutes,
                (prediction.wait_range_low, prediction.wait_range_high),
            )

        recommendation = recommend_slot(
            branch_id,
            predict_slot,
            now=now,
            rotation_index=next_rotation_index(branch_id, intent.service_id),
            horizon_days=horizon_days,
        )
        if recommendation is None:
            return None

        slot = recommendation["slot"]
        slot_start = datetime.fromisoformat(str(slot["start_iso"]))
        pred = prediction_by_slot[slot_start]
        crowd, crowd_label = self._crowd_from_wait(pred.predicted_wait_minutes)

        docs = self.documents_for_service(intent.service_id, user_documents)
        missing = [d.name for d in docs if d.status == "missing" and d.required]

        time_label = f"{slot['start']}–{slot['end']}"
        date_label = str(slot["date"])
        if date_label == now.strftime("%Y-%m-%d"):
            when = f"Today, {time_label}"
        elif date_label == (now + timedelta(days=1)).strftime("%Y-%m-%d"):
            when = f"Tomorrow, {time_label}"
        else:
            when = f"{slot['day']}, {time_label}"

        reason = (
            f"Recommended because {branch['branch_name']} historically has shorter queues "
            f"around {time_label} on {slot['day']}s, is relatively close to your "
            f"location (~{best['distance']:.0f} km), and offers {intent.service_name}."
        )
        if missing:
            ai_rec = (
                f"Arrange your missing document(s) first ({', '.join(missing)}), "
                f"then visit {branch['branch_name']} {when.lower()}. "
                f"Estimated wait {pred.wait_range_low}–{pred.wait_range_high} minutes "
                f"(AI estimate — demo data)."
            )
        else:
            ai_rec = (
                f"Visit {branch['branch_name']} {when.lower()}. "
                f"Estimated wait {pred.wait_range_low}–{pred.wait_range_high} minutes "
                f"(AI estimate based on historical/sample data)."
            )

        rotation = recommendation["rotation"]
        alternatives = []
        for item in recommendation["alternatives"]:
            wait_range = item["wait_range"]
            alternatives.append(
                {
                    "branch_id": branch_id,
                    "branch_name": str(branch["branch_name"]),
                    "day": item["day"],
                    "date": item["date"],
                    "time": f"{item['start']}–{item['end']}",
                    "estimated_wait": item["wait_minutes"],
                    "wait_range": wait_range,
                    "confidence": pred.confidence,
                }
            )

        reports_used = recent_reports_by_branch.get(str(branch["branch_id"]), [])
        hist_rows = 0
        if self.predictor.history is not None:
            hist_rows = int(
                len(
                    self.predictor.history[
                        self.predictor.history["branch_id"] == str(branch["branch_id"])
                    ]
                )
            )

        evidence = {
            "sources": [
                {
                    "type": "historical_sample",
                    "label": "Historical / sample",
                    "value_minutes": pred.historical_estimate,
                    "rows_for_branch": hist_rows,
                    "note": "Pattern-trained observations (branch, day, time, service)",
                },
                {
                    "type": "user_reported",
                    "label": "User-reported",
                    "value_minutes": pred.reported_wait,
                    "reports_used": len(reports_used),
                    "note": "Crowdsourced crowd level / wait — not official DHA data",
                },
                {
                    "type": "ai_predicted",
                    "label": "AI predicted",
                    "value_minutes": pred.predicted_wait_minutes,
                    "range": [pred.wait_range_low, pred.wait_range_high],
                    "confidence": pred.confidence,
                    "note": "scikit-learn model estimate — not a guaranteed wait time",
                },
            ],
            "model": {
                "algorithm": "GradientBoostingRegressor",
                "features": [
                    "branch_id",
                    "day",
                    "hour",
                    "service_id",
                    "is_holiday",
                    "month",
                ],
                "mae_minutes": self.predictor.meta.get("mae_minutes"),
                "rows_trained": self.predictor.meta.get("rows_trained"),
            },
            "live_government_api": False,
        }

        return VisitPlan(
            service_id=intent.service_id,
            service_name=intent.service_name,
            category=intent.category,
            branch_id=str(branch["branch_id"]),
            branch_name=str(branch["branch_name"]),
            city=str(branch["city"]),
            address=str(branch["address"]),
            crowd_level=crowd,
            crowd_label=crowd_label,
            estimated_wait_low=pred.wait_range_low,
            estimated_wait_high=pred.wait_range_high,
            predicted_wait=pred.predicted_wait_minutes,
            recommended_day=str(slot["day"]),
            recommended_date=date_label,
            recommended_time=time_label,
            recommended_text=str(recommendation["recommended_text"]),
            slot=slot,
            rotation=rotation,
            rotation_note=str(recommendation["note"]),
            prediction_confidence=pred.confidence,
            documents=[asdict(d) for d in docs],
            missing_documents=missing,
            reason=reason,
            ai_recommendation=ai_rec,
            data_labels={
                "mode": "Demo Mode",
                "prediction": "AI estimate based on historical/sample data",
                "crowd": "User-reported when available; otherwise model estimate",
                "documents": "Sample checklist for MVP — confirm with Home Affairs",
                "historical": "Historical/sample observations used to train the model",
            },
            prediction_detail=asdict(pred),
            evidence=evidence,
            disclaimer=(
                "This is an AI estimate, not a guaranteed wait time. "
                "Information may change. Verify official requirements, hours and "
                "appointments with Home Affairs before travelling."
            ),
            alternatives=alternatives,
            analysing_steps=[
                {"id": "service", "label": "Service identified", "status": "done"},
                {"id": "branches", "label": "Branches found", "status": "done"},
                {"id": "queue", "label": "Queue data analysed", "status": "done"},
                {"id": "docs", "label": "Documents checked", "status": "done"},
                {"id": "time", "label": "Best time calculated", "status": "done"},
            ],
        )

    def plan_to_dict(self, plan: VisitPlan) -> dict[str, Any]:
        return asdict(plan)
