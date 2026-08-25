"""Non-sensitive service status endpoint."""

from fastapi import APIRouter

from schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Get API health")
def get_health() -> HealthResponse:
    """Return a stable response suitable for local integration checks."""
    return HealthResponse(status="ok", service="ecdat-backend", version="0.1.0")
