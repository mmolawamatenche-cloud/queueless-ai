"""Natural-language service intent classification for Home Affairs MVP."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass
class ServiceIntent:
    service_id: str
    service_name: str
    category: str
    urgency: str
    confidence: float
    requires_appointment: bool
    matched_keywords: list[str]
    explanation: str
    demo_label: str = "AI interpretation from sample service database"


# Phrase patterns ranked by specificity (checked in order)
PATTERNS: list[tuple[str, list[str]]] = [
    (
        "passport_renewal",
        [
            r"renew.*passport",
            r"passport.*renew",
            r"expired passport",
            r"passport renewal",
            r"extend.*passport",
        ],
    ),
    (
        "passport_new",
        [
            r"new passport",
            r"first passport",
            r"get a passport",
            r"apply.*passport",
            r"need a passport",
            r"want a passport",
        ],
    ),
    (
        "id_replacement",
        [
            r"lost.*id",
            r"stolen.*id",
            r"damaged.*id",
            r"replace.*id",
            r"id replacement",
            r"lost my (smart )?id",
            r"id.*lost",
        ],
    ),
    (
        "id_application",
        [
            r"new id",
            r"smart id",
            r"id book",
            r"apply.*id",
            r"get an id",
            r"identity document",
        ],
    ),
    (
        "birth_registration",
        [
            r"register.*(child|baby|birth)",
            r"birth (certificate|registration)",
            r"newborn",
            r"baby.*register",
        ],
    ),
    (
        "marriage_certificate",
        [
            r"marriage",
            r"wedding certificate",
            r"get married",
        ],
    ),
    (
        "death_certificate",
        [
            r"death certificate",
            r"deceased",
        ],
    ),
    (
        "visa_application",
        [
            r"visa",
            r"work permit",
            r"residence permit",
            r"temporary residence",
        ],
    ),
    (
        "learners_license",
        [r"learner'?s? licen[cs]e", r"learners? test"],
    ),
    (
        "drivers_license_new",
        [
            r"new (?:driver'?s? |driving )licen[cs]e",
            r"first(?:-time)? (?:driver'?s? |driving )licen[cs]e",
            r"apply.*(?:driver'?s? |driving )licen[cs]e",
            r"driving test",
        ],
    ),
    (
        "drivers_license_renewal",
        [
            r"renew.*(?:driver'?s? |driving )licen[cs]e",
            r"(?:driver'?s? |driving )licen[cs]e.*renew",
            r"licen[cs]e renewal",
            r"driver'?s? licen[cs]e",
            r"driving licen[cs]e",
        ],
    ),
    (
        "outpatient_queue",
        [
            r"clinic",
            r"doctor",
            r"healthcare",
            r"medical",
        ],
    ),
]


class ServiceClassifier:
    def __init__(self) -> None:
        path = DATA_DIR / "services.csv"
        self.services = pd.read_csv(path).set_index("service_id")

    def classify(self, text: str) -> ServiceIntent:
        cleaned = (text or "").strip().lower()
        if not cleaned:
            return self._fallback("Please describe what you need help with.")

        best_id: str | None = None
        best_score = 0.0
        matched: list[str] = []

        for service_id, patterns in PATTERNS:
            if service_id not in self.services.index:
                continue
            hits = []
            for pat in patterns:
                if re.search(pat, cleaned):
                    hits.append(pat)
            if hits:
                # Longer / more specific matches score higher
                score = 0.55 + 0.12 * len(hits) + 0.05 * max(len(h) for h in hits) / 20
                if service_id in cleaned or service_id.replace("_", " ") in cleaned:
                    score += 0.15
                if score > best_score:
                    best_score = min(score, 0.96)
                    best_id = service_id
                    matched = hits

        # Keyword fallback from CSV
        if best_id is None:
            for sid, row in self.services.iterrows():
                keywords = [k.strip() for k in str(row["keywords"]).split(",") if k.strip()]
                hits = [k for k in keywords if k in cleaned]
                if hits:
                    score = 0.45 + 0.1 * len(hits)
                    if score > best_score:
                        best_score = min(score, 0.85)
                        best_id = str(sid)
                        matched = hits

        if best_id is None or best_id not in self.services.index:
            return self._fallback(
                "I couldn't identify a matching service yet. "
                "Try: 'I need to renew my passport', 'I need to renew my driver's licence', "
                "or 'I need help with my SASSA grant'."
            )

        row = self.services.loc[best_id]
        urgency = str(row["urgency_default"])
        if any(w in cleaned for w in ("urgent", "asap", "emergency", "today")):
            urgency = "high"

        explanation = (
            f"Matched your request to «{row['service_name']}» "
            f"({row['category']}) using service patterns"
            + (f": {', '.join(matched[:3])}." if matched else ".")
        )

        return ServiceIntent(
            service_id=str(best_id),
            service_name=str(row["service_name"]),
            category=str(row["category"]),
            urgency=urgency,
            confidence=round(best_score, 2),
            requires_appointment=bool(row["requires_appointment"])
            if isinstance(row["requires_appointment"], bool)
            else str(row["requires_appointment"]).lower() == "true",
            matched_keywords=matched[:5],
            explanation=explanation,
        )

    def _fallback(self, message: str) -> ServiceIntent:
        return ServiceIntent(
            service_id="",
            service_name="Unknown",
            category="Home Affairs",
            urgency="normal",
            confidence=0.0,
            requires_appointment=False,
            matched_keywords=[],
            explanation=message,
        )

    def to_dict(self, intent: ServiceIntent) -> dict[str, Any]:
        return asdict(intent)
