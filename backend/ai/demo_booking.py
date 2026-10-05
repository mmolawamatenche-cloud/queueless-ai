import random
import string
from datetime import datetime, timedelta


def generate_reference() -> str:
    return "QL-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def create_demo_booking(service: str, branch: str, preferred_time: str | None = None) -> dict:
    """
    Simulates a booking. Nothing here touches any real government system —
    it exists only inside QueueLess's own database, for demo/comparison purposes.
    """
    slot_time = preferred_time or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d 09:00")
    return {
        "demo": True,
        "reference": generate_reference(),
        "service": service,
        "branch": branch,
        "slot_time": slot_time,
        "status": "Simulated — not a real appointment",
        "disclaimer": "This is a QueueLess AI demo booking. It is not connected to Home Affairs, SARS, or any government system.",
    }
