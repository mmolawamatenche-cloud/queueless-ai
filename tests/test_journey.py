"""Basic journey tests for QueueLess AI."""
from backend.ai.demo_booking import create_demo_booking
from backend.ai.recommendation_engine import RecommendationEngine
from backend.ai.service_classifier import ServiceClassifier
from backend.ai.queue_predictor import QueuePredictor


def test_demo_booking_payload():
    booking = create_demo_booking("passport_renewal", "jhb_cbd", "2026-10-01 09:00")
    assert booking["demo"] is True
    assert booking["service"] == "passport_renewal"
    assert booking["branch"] == "jhb_cbd"
    assert "QL-" in booking["reference"]
    assert "not connected" in booking["disclaimer"].lower()


def test_passport_renewal_intent():
    c = ServiceClassifier()
    intent = c.classify("I need to renew my passport.")
    assert intent.service_id == "passport_renewal"
    assert intent.confidence > 0.5


def test_lost_id_intent():
    c = ServiceClassifier()
    intent = c.classify("I lost my ID")
    assert intent.service_id == "id_replacement"


def test_driver_license_renewal_intent():
    c = ServiceClassifier()
    intent = c.classify("I need to renew my driving licence")
    assert intent.service_id == "drivers_license_renewal"


def test_new_driver_license_intent():
    c = ServiceClassifier()
    intent = c.classify("I need to apply for a new driver's licence")
    assert intent.service_id == "drivers_license_new"


def test_clinic_visit_intent():
    c = ServiceClassifier()
    intent = c.classify("I need to visit a clinic")
    assert intent.service_id == "outpatient_queue"


def test_recommendation_plan():
    p = QueuePredictor()
    e = RecommendationEngine(p)
    c = ServiceClassifier()
    intent = c.classify("I need to renew my passport")
    plan = e.build_plan(intent, location="Johannesburg")
    assert plan is not None
    assert plan.branch_name
    assert plan.estimated_wait_low <= plan.estimated_wait_high
    assert "Appointment confirmation" in plan.missing_documents
    assert plan.data_labels["mode"] == "Demo Mode"
