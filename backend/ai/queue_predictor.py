"""Queue wait-time prediction using scikit-learn on sample historical data."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"
MODEL_PATH = MODEL_DIR / "queue_model.pkl"
META_PATH = MODEL_DIR / "queue_model_meta.json"

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
CROWD_TO_WAIT = {"low": 25, "medium": 55, "high": 95}


@dataclass
class PredictionResult:
    predicted_wait_minutes: int
    wait_range_low: int
    wait_range_high: int
    confidence: float
    label: str
    historical_estimate: int | None
    reported_wait: int | None
    crowd_adjustment: int
    explanation: str
    is_demo: bool = True


class QueuePredictor:
    def __init__(self) -> None:
        self.pipeline: Pipeline | None = None
        self.meta: dict[str, Any] = {}
        self.history: pd.DataFrame | None = None
        self._load_or_train()

    def _load_history(self) -> pd.DataFrame:
        path = DATA_DIR / "queue_data.csv"
        if not path.exists():
            from backend.data.generate_queue_data import main as gen

            gen()
        df = pd.read_csv(path)
        df["hour_num"] = df["hour"].astype(str).str.slice(0, 2).astype(int)
        return df

    def train(self) -> dict[str, Any]:
        df = self._load_history()
        self.history = df
        features = ["branch_id", "day", "hour_num", "service_id", "is_holiday", "month"]
        X = df[features]
        y = df["wait_minutes"]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        pre = ColumnTransformer(
            [
                (
                    "cat",
                    OneHotEncoder(handle_unknown="ignore"),
                    ["branch_id", "day", "service_id"],
                ),
                ("num", "passthrough", ["hour_num", "is_holiday", "month"]),
            ]
        )
        model = GradientBoostingRegressor(
            n_estimators=120,
            max_depth=3,
            learning_rate=0.08,
            random_state=42,
        )
        pipe = Pipeline([("pre", pre), ("model", model)])
        pipe.fit(X_train, y_train)
        preds = pipe.predict(X_test)
        mae = float(mean_absolute_error(y_test, preds))

        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipe, MODEL_PATH)
        self.pipeline = pipe
        self.meta = {
            "mae_minutes": round(mae, 2),
            "rows_trained": int(len(df)),
            "label": "AI estimate based on historical/sample data",
            "accuracy_note": f"Demo model MAE ~ {mae:.1f} minutes on hold-out sample",
        }
        import json

        META_PATH.write_text(json.dumps(self.meta, indent=2), encoding="utf-8")
        return self.meta

    def _load_or_train(self) -> None:
        import json

        if MODEL_PATH.exists():
            try:
                self.pipeline = joblib.load(MODEL_PATH)
            except Exception:
                self.train()
                return
            if META_PATH.exists():
                self.meta = json.loads(META_PATH.read_text(encoding="utf-8"))
            self.history = self._load_history()
        else:
            self.train()

    def historical_average(
        self, branch_id: str, day: str, hour: int, service_id: str
    ) -> int | None:
        if self.history is None:
            self.history = self._load_history()
        subset = self.history[
            (self.history["branch_id"] == branch_id)
            & (self.history["day"] == day)
            & (self.history["hour_num"] == hour)
            & (self.history["service_id"] == service_id)
        ]
        if subset.empty:
            subset = self.history[
                (self.history["branch_id"] == branch_id)
                & (self.history["hour_num"] == hour)
            ]
        if subset.empty:
            return None
        return int(round(subset["wait_minutes"].mean()))

    def predict(
        self,
        branch_id: str,
        day: str,
        hour: int,
        service_id: str,
        month: int | None = None,
        is_holiday: bool = False,
        recent_reports: list[dict[str, Any]] | None = None,
    ) -> PredictionResult:
        if self.pipeline is None:
            self.train()

        from datetime import datetime

        month = month or datetime.now().month
        day_name = day if day in DAY_ORDER else "Wednesday"

        X = pd.DataFrame(
            [
                {
                    "branch_id": branch_id,
                    "day": day_name,
                    "hour_num": hour,
                    "service_id": service_id,
                    "is_holiday": int(is_holiday),
                    "month": month,
                }
            ]
        )
        raw = float(self.pipeline.predict(X)[0])  # type: ignore[union-attr]
        historical = self.historical_average(branch_id, day_name, hour, service_id)

        crowd_adj = 0
        reported_wait: int | None = None
        if recent_reports:
            levels = [r.get("crowd_level") for r in recent_reports if r.get("crowd_level")]
            waits = [
                r.get("wait_minutes")
                for r in recent_reports
                if r.get("wait_minutes") is not None
            ]
            if waits:
                reported_wait = int(round(sum(waits) / len(waits)))
            if levels:
                mapped = [CROWD_TO_WAIT.get(str(l).lower(), 55) for l in levels]
                crowd_mean = sum(mapped) / len(mapped)
                crowd_adj = int(round(crowd_mean - raw))
                # Blend toward crowd signal without overwriting model
                raw = 0.65 * raw + 0.35 * crowd_mean

        predicted = int(max(10, min(180, round(raw))))
        # Confidence declines when crowd reports disagree with history
        base_conf = 0.82
        if recent_reports:
            base_conf = min(0.9, base_conf + 0.03 * min(len(recent_reports), 3))
            if abs(crowd_adj) > 30:
                base_conf -= 0.08
        mae = float(self.meta.get("mae_minutes", 12))
        low = max(10, int(predicted - mae * 1.1))
        high = int(predicted + mae * 1.1)

        parts = [
            f"Model estimate for {branch_id} on {day_name} at {hour:02d}:00 "
            f"is ~{predicted} minutes"
        ]
        if historical is not None:
            parts.append(f"historical average nearby: {historical} min")
        if recent_reports:
            parts.append(
                f"{len(recent_reports)} recent user report(s) adjusted the estimate"
            )
        parts.append("This is an AI estimate — not a guaranteed wait time.")

        return PredictionResult(
            predicted_wait_minutes=predicted,
            wait_range_low=low,
            wait_range_high=high,
            confidence=round(max(0.45, min(0.92, base_conf)), 2),
            label="AI prediction (demo / sample data)",
            historical_estimate=historical,
            reported_wait=reported_wait,
            crowd_adjustment=crowd_adj,
            explanation="; ".join(parts),
            is_demo=True,
        )

    def to_dict(self, result: PredictionResult) -> dict[str, Any]:
        return asdict(result)
