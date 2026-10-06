"""QueueLess AI — FastAPI application (AI-first service-access assistant)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.ai.demo_booking import create_demo_booking
from backend.ai.queue_predictor import QueuePredictor
from backend.ai.recommendation_engine import RecommendationEngine
from backend.ai.service_classifier import ServiceClassifier
from backend.database import database as db

FRONTEND = ROOT / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    if not db.list_queue_reports(limit=1):
        db.add_queue_report("jhb_cbd", "medium", 48, "passport_renewal")
        db.add_queue_report("soweto", "low", 28, "id_replacement")
        db.add_queue_report("pta_cbd", "high", 95, "passport_renewal")
        db.add_queue_report("randburg", "low", 32, "passport_renewal")
    yield


app = FastAPI(
    title="QueueLess AI",
    description="AI-powered South African service-access assistant — Know Before You Go.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

classifier = ServiceClassifier()
predictor = QueuePredictor()
engine = RecommendationEngine(predictor=predictor)


class AssistRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language request")
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    documents_on_hand: list[str] = Field(default_factory=list)


class ReportRequest(BaseModel):
    branch_id: str
    crowd_level: str
    wait_minutes: int | None = None
    service_id: str | None = None


class ClassifyRequest(BaseModel):
    query: str


class FeedbackRequest(BaseModel):
    useful: bool
    comment: str | None = None
    plan_id: int | None = None


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "app": "QueueLess AI",
        "tagline": "Know Before You Go.",
        "mode": "Demo Mode",
        "model": predictor.meta,
        "privacy": "MVP stores no ID/passport images — checklist only",
    }


@app.get("/api/credibility")
def credibility() -> dict[str, Any]:
    """Judge-facing transparency: how predictions are produced."""
    hist_rows = 0
    if predictor.history is not None:
        hist_rows = int(len(predictor.history))
    return {
        "judge_answer": (
            "The MVP combines historical observations with crowdsourced reports. "
            "A scikit-learn Gradient Boosting model analyses branch, service, day and "
            "time patterns and generates an explicitly labelled prediction — never "
            "presented as a live government queue guarantee."
        ),
        "pipeline": [
            "Historical / sample observations (CSV)",
            "User queue reports (SQLite)",
            "Time / day / branch / service features",
            "ML wait-time prediction",
            "AI recommendation + document checklist",
        ],
        "labels": {
            "reported": "User-submitted crowd / wait",
            "predicted": "ML estimate (range + confidence)",
            "demo_sample": "Training data — not a live DHA API",
        },
        "model": predictor.meta,
        "historical_rows": hist_rows,
        "branches": int(len(engine.branches)),
        "services_home_affairs_focus": True,
        "live_government_api": False,
        "privacy": {
            "stores_identity_documents": False,
            "document_feature": "Checklist only (no ID/passport upload in MVP)",
        },
        "impact_problem": (
            "Wasted trips: travel far, wait long, discover a missing document, return another day."
        ),
    }


@app.post("/api/classify")
def classify(body: ClassifyRequest) -> dict[str, Any]:
    intent = classifier.classify(body.query)
    return classifier.to_dict(intent)


@app.post("/api/assist")
def assist(body: AssistRequest) -> dict[str, Any]:
    """Full AI journey: understand → analyse → recommend."""
    db.touch_session()
    intent = classifier.classify(body.query)
    if not intent.service_id:
        return {
            "ok": False,
            "intent": classifier.to_dict(intent),
            "plan": None,
            "message": intent.explanation,
        }

    reports_by_branch: dict[str, list] = {}
    for branch_id in engine.branches["branch_id"].astype(str):
        reports_by_branch[branch_id] = db.recent_reports_for_branch(branch_id)

    plan = engine.build_plan(
        intent=intent,
        location=body.location,
        lat=body.latitude,
        lon=body.longitude,
        user_documents=body.documents_on_hand,
        recent_reports_by_branch=reports_by_branch,
    )
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail="No branches found for this service in the demo database.",
        )

    plan_dict = engine.plan_to_dict(plan)
    db.save_plan(body.query, intent.service_id, plan_dict)

    return {
        "ok": True,
        "intent": classifier.to_dict(intent),
        "plan": plan_dict,
        "message": "Here's the best plan for you.",
        "demo_notice": (
            "Demo prediction based on historical/sample data and user reports — "
            "not a live government queue feed."
        ),
        "credibility": {
            "live_government_api": False,
            "not_a_guarantee": True,
        },
    }


@app.get("/api/branches")
def branches() -> list[dict[str, Any]]:
    return engine.branches.to_dict(orient="records")


@app.get("/api/services")
def services() -> list[dict[str, Any]]:
    import pandas as pd

    path = ROOT / "backend" / "data" / "services.csv"
    return pd.read_csv(path).to_dict(orient="records")


@app.get("/api/documents")
def documents(service_id: str | None = None) -> list[dict[str, Any]]:
    rows = engine.documents
    if service_id:
        rows = rows[rows["service_id"].astype(str) == service_id]
    return rows.to_dict(orient="records")


@app.post("/api/reports")
def create_report(body: ReportRequest) -> dict[str, Any]:
    level = body.crowd_level.lower().strip()
    if level not in {"low", "medium", "high"}:
        raise HTTPException(status_code=400, detail="crowd_level must be low|medium|high")
    report = db.add_queue_report(
        branch_id=body.branch_id,
        crowd_level=level,
        wait_minutes=body.wait_minutes,
        service_id=body.service_id,
    )
    # Return updated prediction for this branch (demo impact)
    from datetime import datetime

    now = datetime.now()
    service_id = body.service_id or "passport_renewal"
    pred = predictor.predict(
        branch_id=body.branch_id,
        day=now.strftime("%A"),
        hour=max(8, min(15, now.hour)),
        service_id=service_id,
        recent_reports=db.recent_reports_for_branch(body.branch_id),
    )
    return {
        "ok": True,
        "message": "Thank you. Your report will help improve QueueLess AI's predictions.",
        "report": report,
        "updated_prediction": predictor.to_dict(pred),
        "label": "User-reported data combined with AI historical estimate",
    }


@app.post("/api/demo-booking")
def demo_booking(service: str, branch: str, preferred_time: str | None = None) -> dict[str, Any]:
    booking = create_demo_booking(service=service, branch=branch, preferred_time=preferred_time)
    db.save_demo_booking(booking)
    return booking


@app.get("/api/reports")
def get_reports(limit: int = 50) -> list[dict[str, Any]]:
    return db.list_queue_reports(limit=limit)


@app.get("/api/history")
def history(limit: int = 20) -> list[dict[str, Any]]:
    return db.list_plans(limit=limit)


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    stats = db.dashboard_stats()
    stats["prediction_model"] = predictor.meta
    stats["prediction_accuracy"] = {
        "metric": "MAE (demo hold-out)",
        "value_minutes": predictor.meta.get("mae_minutes"),
        "note": predictor.meta.get("accuracy_note"),
    }
    hist_rows = int(len(predictor.history)) if predictor.history is not None else 0
    stats["pipeline"] = {
        "historical_rows": hist_rows,
        "algorithm": "GradientBoostingRegressor",
        "features": ["branch", "day", "hour", "service", "holiday", "month"],
        "blends_user_reports": True,
    }
    # Enrich branch names
    name_map = {
        str(r["branch_id"]): str(r["branch_name"])
        for _, r in engine.branches.iterrows()
    }
    for item in stats["top_branches"]:
        item["branch_name"] = name_map.get(item["branch_id"], item["branch_id"])
    for item in stats["current_crowd_reports"]:
        item["branch_name"] = name_map.get(item["branch_id"], item["branch_id"])
    return stats


@app.post("/api/feedback")
def feedback(body: FeedbackRequest) -> dict[str, Any]:
    result = db.add_feedback(body.useful, body.comment, body.plan_id)
    return {
        "ok": True,
        "message": "Thanks — your feedback strengthens traction evidence for QueueLess AI.",
        "feedback": result,
        "stats": db.feedback_stats(),
    }


@app.post("/api/predict")
def predict_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    branch_id = payload.get("branch_id", "jhb_cbd")
    day = payload.get("day", "Wednesday")
    hour = int(payload.get("hour", 14))
    service_id = payload.get("service_id", "passport_renewal")
    reports = db.recent_reports_for_branch(branch_id)
    result = predictor.predict(
        branch_id=branch_id,
        day=day,
        hour=hour,
        service_id=service_id,
        recent_reports=reports,
    )
    return predictor.to_dict(result)


# Static frontend
if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


@app.get("/{page}.html")
def html_page(page: str) -> FileResponse:
    path = FRONTEND / f"{page}.html"
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path)
