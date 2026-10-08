from backend.institutions import (
    INSTITUTIONS,
    Institution,
    Service,
    build_message,
    create_visit_plan,
    find_institution,
    find_service,
    get_all_institutions,
    get_queue_status,
)
from backend.main import app

__all__ = [
    "app",
    "INSTITUTIONS",
    "Institution",
    "Service",
    "build_message",
    "create_visit_plan",
    "find_institution",
    "find_service",
    "get_all_institutions",
    "get_queue_status",
]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
