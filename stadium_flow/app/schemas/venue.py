"""
Venue-related request and response schemas.

Pydantic models for API endpoint input validation and
response serialization.
"""

from pydantic import BaseModel, Field
from typing import Optional


class VenueResponse(BaseModel):
    """Response schema for venue details."""
    id: str
    name: str
    venue_type: str
    max_capacity: int
    current_total_occupancy: int = 0
    occupancy_percentage: float = 0.0
    total_zones: int = 0
    active_alerts: int = 0
    is_active: bool = True

    model_config = {"json_schema_extra": {
        "example": {
            "id": "narendra-modi-stadium",
            "name": "Narendra Modi Stadium",
            "venue_type": "stadium",
            "max_capacity": 132000,
            "current_total_occupancy": 45000,
            "occupancy_percentage": 34.1,
            "total_zones": 24,
            "active_alerts": 2,
            "is_active": True,
        }
    }}


class VenueStatsResponse(BaseModel):
    """Aggregated venue statistics for the dashboard."""
    total_capacity: int
    current_occupancy: int
    occupancy_percentage: float
    zones_clear: int = 0
    zones_moderate: int = 0
    zones_busy: int = 0
    zones_critical: int = 0
    avg_wait_time_minutes: float = 0.0
    active_alerts: int = 0
    attendees_served: int = 0
    peak_occupancy: int = 0


class HealthResponse(BaseModel):
    """API health check response."""
    status: str = "healthy"
    version: str
    simulation_active: bool = False
    connected_clients: int = 0
    uptime_seconds: float = 0.0
