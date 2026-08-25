"""System endpoint contracts."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Public response for the health endpoint."""

    status: str
    service: str
    version: str
