"""
Venue API routes.

Provides endpoints for venue information, statistics, and health checks.
"""

import time
from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.venue import HealthResponse, VenueResponse, VenueStatsResponse

router = APIRouter(prefix="/venues", tags=["Venues"])


@router.get(
    "/info",
    response_model=VenueResponse,
    summary="Get venue information",
    description="Returns current venue details including occupancy and alert count.",
)
async def get_venue_info() -> VenueResponse:
    """Get current venue information and stats."""
    from app.main import simulation_engine

    state = simulation_engine.get_state()
    metrics = state["metrics"]

    zones = simulation_engine.get_all_zones()
    critical_count = sum(1 for z in zones if z.status.value == "critical")

    return VenueResponse(
        id="narendra-modi-stadium",
        name="Narendra Modi Stadium",
        venue_type="stadium",
        max_capacity=132000,
        current_total_occupancy=metrics["total_attendees"],
        occupancy_percentage=metrics["occupancy_percentage"],
        total_zones=len(zones),
        active_alerts=critical_count,
        is_active=True,
    )


@router.get(
    "/stats",
    response_model=VenueStatsResponse,
    summary="Get detailed venue statistics",
    description="Returns aggregated venue statistics for the dashboard.",
)
async def get_venue_stats() -> VenueStatsResponse:
    """Get detailed venue statistics for the dashboard."""
    from app.main import simulation_engine, crowd_analytics

    state = simulation_engine.get_state()
    metrics = state["metrics"]
    zones = simulation_engine.get_all_zones()
    summary = crowd_analytics.get_congestion_summary()

    # Compute average wait time across concourse zones
    concourse_zones = [z for z in zones if z.zone_type.value == "concourse"]
    avg_wait = sum(
        crowd_analytics.estimate_wait_time(z.id) for z in concourse_zones
    ) / max(len(concourse_zones), 1)

    return VenueStatsResponse(
        total_capacity=metrics["max_capacity"],
        current_occupancy=metrics["total_attendees"],
        occupancy_percentage=metrics["occupancy_percentage"],
        zones_clear=summary["status_distribution"].get("clear", 0),
        zones_moderate=summary["status_distribution"].get("moderate", 0),
        zones_busy=summary["status_distribution"].get("busy", 0),
        zones_critical=summary["status_distribution"].get("critical", 0),
        avg_wait_time_minutes=round(avg_wait, 1),
        active_alerts=metrics["critical_zones"],
        attendees_served=metrics["total_served"],
        peak_occupancy=metrics["peak_occupancy"],
    )
