"""QueueLess AI institution + queue intelligence layer.

This module provides the demo institution catalog and lightweight service
matching used to power the MVP "Know Before You Go" experience.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass
class Service:
    name: str
    bookable: bool
    documents: list[str]


@dataclass
class Institution:
    id: int
    name: str
    category: str
    description: str
    services: list[Service]
    queue_status: str
    estimated_wait_minutes: int
    data_source: str = "DEMO"


INSTITUTIONS: list[Institution] = [
    Institution(
        id=1,
        name="Department of Home Affairs",
        category="Government",
        description="Identity, passport, citizenship and civil registration services.",
        queue_status="Yellow",
        estimated_wait_minutes=55,
        services=[
            Service("ID Application / Replacement", True, ["Identity documents", "Required application documents"]),
            Service("Passport Application", True, ["South African ID", "Required passport documents"]),
            Service("Birth Certificate Services", False, ["Required birth registration documents"]),
        ],
    ),
    Institution(
        id=2,
        name="Licensing Department / DLTC",
        category="Transport",
        description="Driver and vehicle licensing services.",
        queue_status="Red",
        estimated_wait_minutes=95,
        services=[
            Service("Learner's Licence", True, ["Identity document", "Required photographs", "Application forms"]),
            Service("Driver's Licence", True, ["Identity document", "Required licence documents"]),
            Service("Vehicle Registration", False, ["Vehicle documents", "Identity document"]),
        ],
    ),
    Institution(
        id=3,
        name="Municipal Offices",
        category="Municipality",
        description="Municipal accounts, permits and local government services.",
        queue_status="Yellow",
        estimated_wait_minutes=45,
        services=[
            Service("Municipal Account Assistance", False, ["Account information", "Identity document"]),
            Service("Permit Application", True, ["Identity document", "Supporting documents"]),
            Service("Municipal Enquiry", False, ["Account/reference information"]),
        ],
    ),
    Institution(
        id=4,
        name="Public Clinics & Hospitals",
        category="Healthcare",
        description="Public healthcare registration, appointments and services.",
        queue_status="Red",
        estimated_wait_minutes=120,
        services=[
            Service("Clinic Registration", False, ["Identity document", "Relevant medical information"]),
            Service("Medical Appointment", True, ["Patient information", "Identity document where required"]),
        ],
    ),
    Institution(
        id=5,
        name="SARS",
        category="Government",
        description="Taxpayer and revenue services.",
        queue_status="Green",
        estimated_wait_minutes=25,
        services=[
            Service("Taxpayer Assistance", True, ["Identity document", "Tax/reference information"]),
            Service("Tax Registration", True, ["Identity document", "Supporting tax documents"]),
        ],
    ),
    Institution(
        id=6,
        name="SASSA",
        category="Social Services",
        description="Social grants and related assistance.",
        queue_status="Red",
        estimated_wait_minutes=90,
        services=[
            Service("Grant Application", False, ["Identity document", "Supporting documents"]),
            Service("Grant Enquiry", False, ["Identity document", "Grant/reference information"]),
        ],
    ),
    Institution(
        id=7,
        name="Universities & TVET Colleges",
        category="Education",
        description="Admissions, registration and student administration.",
        queue_status="Yellow",
        estimated_wait_minutes=50,
        services=[
            Service("Student Registration", True, ["Student number", "Identity document", "Registration documents"]),
            Service("Admissions Enquiry", True, ["Application/reference number", "Identity document"]),
        ],
    ),
    Institution(
        id=8,
        name="Banks",
        category="Financial Services",
        description="Branch-based banking and customer services.",
        queue_status="Green",
        estimated_wait_minutes=20,
        services=[
            Service("Account Assistance", True, ["Identity document", "Banking information"]),
            Service("Card Assistance", False, ["Identity document", "Bank account/card information"]),
        ],
    ),
    Institution(
        id=9,
        name="Post Offices",
        category="Postal Services",
        description="Postal, parcel and selected public services.",
        queue_status="Yellow",
        estimated_wait_minutes=40,
        services=[
            Service("Parcel Collection", False, ["Collection notice", "Identity document"]),
            Service("Postal Service", False, ["Required postal information"]),
        ],
    ),
    Institution(
        id=10,
        name="SAPS Service Centres",
        category="Public Safety",
        description="Police-related administrative and public services.",
        queue_status="Green",
        estimated_wait_minutes=30,
        services=[
            Service("Affidavit", False, ["Identity document", "Relevant information"]),
            Service("Certificate / Enquiry", False, ["Identity document", "Supporting information"]),
        ],
    ),
]


def get_all_institutions() -> list[dict[str, Any]]:
    """Return all institutions."""
    return [asdict(institution) for institution in INSTITUTIONS]


def find_institution(search: str) -> Optional[Institution]:
    """Find an institution by name or category keyword."""
    query = (search or "").lower().strip()
    if not query:
        return None

    for institution in INSTITUTIONS:
        if query in institution.name.lower() or query in institution.category.lower():
            return institution
    return None


def find_service(service_query: str) -> list[dict[str, Any]]:
    """Search all institutions for a service match."""
    query = (service_query or "").lower().strip()
    if not query:
        return []

    matches: list[dict[str, Any]] = []
    for institution in INSTITUTIONS:
        for service in institution.services:
            if query in service.name.lower():
                matches.append(
                    {
                        "institution": institution.name,
                        "service": service.name,
                        "bookable": service.bookable,
                        "documents": service.documents,
                        "queue_status": institution.queue_status,
                        "estimated_wait": institution.estimated_wait_minutes,
                    }
                )
    return matches


def get_queue_status(institution_name: str) -> dict[str, Any]:
    """Return the queue summary for a named institution."""
    institution = find_institution(institution_name)
    if not institution:
        return {"error": "Institution not found"}
    return {
        "institution": institution.name,
        "status": institution.queue_status,
        "estimated_wait_minutes": institution.estimated_wait_minutes,
        "data_source": institution.data_source,
    }


def create_visit_plan(user_request: str) -> dict[str, Any]:
    """Create a simple AI-style plan using keyword matching."""
    request = (user_request or "").lower()
    if not request:
        return {
            "success": False,
            "user_request": user_request,
            "message": "I could not confidently identify the service. Please tell me what you need help with.",
        }

    keyword_map = {
        "passport": "passport",
        "id": "id",
        "identity": "id",
        "driver": "driver",
        "licence": "licence",
        "license": "licence",
        "vehicle": "vehicle",
        "tax": "tax",
        "sars": "tax",
        "grant": "grant",
        "sassa": "grant",
        "university": "student",
        "student": "student",
        "college": "student",
        "bank": "bank",
        "card": "card",
        "parcel": "parcel",
        "post": "postal",
        "affidavit": "affidavit",
        "police": "affidavit",
        "clinic": "clinic",
        "hospital": "medical",
        "municipal": "municipal",
    }

    detected = None
    for keyword, service_keyword in keyword_map.items():
        if keyword in request:
            detected = service_keyword
            break

    if detected:
        matches = find_service(detected)
        if matches:
            best = matches[0]
            plan = {
                "success": True,
                "user_request": user_request,
                "recommended_institution": best["institution"],
                "service": best["service"],
                "queue_status": best["queue_status"],
                "estimated_wait_minutes": best["estimated_wait"],
                "bookable": best["bookable"],
                "documents": best["documents"],
                "data_source": "DEMO",
                "message": build_message(best),
            }
            return plan

    return {
        "success": False,
        "user_request": user_request,
        "message": "I could not confidently identify the service. Please tell me what you need help with.",
    }


def build_message(result: dict[str, Any]) -> str:
    """Build a friendly human-readable recommendation summary."""
    booking = (
        "This service appears to be bookable."
        if result.get("bookable")
        else "This service is currently shown as walk-in/non-bookable in the demo."
    )
    return (
        f"Recommended institution: {result['institution']}\n"
        f"Service: {result['service']}\n"
        f"Queue: {result['queue_status']}\n"
        f"Estimated wait: {result['estimated_wait']} minutes\n"
        f"{booking}\n"
        f"Bring: {', '.join(result['documents'])}"
    )


__all__ = [
    "Service",
    "Institution",
    "INSTITUTIONS",
    "get_all_institutions",
    "find_institution",
    "find_service",
    "get_queue_status",
    "create_visit_plan",
    "build_message",
]
