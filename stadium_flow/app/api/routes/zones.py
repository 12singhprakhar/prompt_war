"""
Zone API routes.

Provides endpoints for zone status, heatmaps, and predictions.
"""

from fastapi import APIRouter, HTTPException

from app.schemas.zone import ZoneListResponse, ZoneResponse

router = APIRouter(prefix="/zones", tags=["Zones"])


@router.get(
    "/",
    response_model=ZoneListResponse,
    summary="List all zones",
    description="Get the current status of all zones in the venue.",
)
async def list_zones() -> ZoneListResponse:
    """List all zones with current occupancy and status."""
    from app.main import simulation_engine

    zones = simulation_engine.get_all_zones()
    zone_responses = [
        ZoneResponse(**zone.to_dict()) for zone in zones
    ]
    return ZoneListResponse(zones=zone_responses, total=len(zone_responses))


@router.get(
    "/{zone_id}",
    response_model=ZoneResponse,
    summary="Get zone details",
    description="Get detailed status for a specific zone.",
)
async def get_zone(zone_id: str) -> ZoneResponse:
    """Get detailed status for a specific zone."""
    from app.main import simulation_engine

    zone = simulation_engine.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found")
    return ZoneResponse(**zone.to_dict())


@router.get(
    "/analytics/heatmap",
    summary="Get crowd heatmap",
    description="Get crowd density heatmap data for visualization.",
)
async def get_heatmap() -> dict:
    """Get crowd density heatmap data."""
    from app.main import crowd_analytics
    return {"heatmap": crowd_analytics.compute_heatmap()}


@router.get(
    "/{zone_id}/prediction",
    summary="Get zone congestion prediction",
    description="Predict future congestion for a specific zone.",
)
async def get_prediction(zone_id: str) -> dict:
    """Get congestion prediction for a zone."""
    from app.main import simulation_engine, crowd_analytics

    zone = simulation_engine.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found")

    return crowd_analytics.predict_congestion(zone_id)


@router.get(
    "/analytics/recommendations",
    summary="Get actionable recommendations",
    description="Get AI-generated recommendations for crowd management.",
)
async def get_recommendations() -> dict:
    """Get actionable crowd management recommendations."""
    from app.main import crowd_analytics
    return {"recommendations": crowd_analytics.get_recommendations()}
