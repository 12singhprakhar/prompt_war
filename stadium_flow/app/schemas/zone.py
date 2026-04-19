"""
Zone-related request and response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ZoneResponse(BaseModel):
    """Response schema for zone status."""
    id: str
    name: str
    zone_type: str
    capacity: int
    current_occupancy: int
    occupancy_ratio: float = Field(ge=0.0, le=1.0)
    status: str
    available_capacity: int
    is_accessible: bool
    adjacent_zones: list[str] = []
    map_x: float = 0.0
    map_y: float = 0.0


class ZoneListResponse(BaseModel):
    """Response schema for list of zones."""
    zones: list[ZoneResponse]
    total: int


class ZoneUpdateRequest(BaseModel):
    """Request to manually update zone occupancy (staff use)."""
    occupancy_delta: int = Field(
        description="Change in occupancy (positive = add, negative = remove)"
    )
    reason: Optional[str] = Field(
        default=None, description="Reason for manual adjustment"
    )
