"""
Routing-related request and response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional


class RouteRequest(BaseModel):
    """Request for pathfinding between two zones."""
    origin_zone: str = Field(description="Starting zone ID")
    destination_zone: str = Field(description="Target zone ID")
    accessible_only: bool = Field(
        default=False,
        description="If True, only use ADA-accessible routes",
    )
    avoid_congested: bool = Field(
        default=True,
        description="If True, avoid zones above congestion threshold",
    )

    model_config = {"json_schema_extra": {
        "example": {
            "origin_zone": "gate-1",
            "destination_zone": "block-d",
            "accessible_only": False,
            "avoid_congested": True,
        }
    }}


class RouteStep(BaseModel):
    """Single step in a navigation route."""
    zone_id: str
    zone_name: str
    instruction: str
    distance_meters: float = 0.0
    congestion_status: str = "clear"


class RouteResponse(BaseModel):
    """Complete routing response."""
    origin: str
    destination: str
    steps: list[RouteStep]
    total_distance_meters: float
    estimated_time_minutes: float
    is_accessible: bool
    congestion_avoided: bool
    alternative_available: bool = False
