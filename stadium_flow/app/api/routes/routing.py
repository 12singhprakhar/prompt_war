"""
Routing API endpoints.

Provides navigation pathfinding between zones with congestion
awareness and accessibility support.
"""

from fastapi import APIRouter, HTTPException

from app.schemas.routing import RouteRequest, RouteResponse

router = APIRouter(prefix="/routing", tags=["Navigation"])


@router.post(
    "/find",
    response_model=RouteResponse,
    summary="Find optimal route",
    description="Find the optimal route between two zones with congestion awareness.",
)
async def find_route(request: RouteRequest) -> RouteResponse:
    """Find optimal route between zones using Dijkstra's algorithm."""
    from app.main import routing_engine

    result = routing_engine.find_route(
        origin=request.origin_zone,
        destination=request.destination_zone,
        accessible_only=request.accessible_only,
        avoid_congested=request.avoid_congested,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No route found from '{request.origin_zone}' to '{request.destination_zone}'",
        )

    return RouteResponse(**result)


@router.get(
    "/find",
    response_model=RouteResponse,
    summary="Find optimal route (GET)",
    description="Find the optimal route between two zones via query parameters.",
)
async def find_route_get(
    start_zone_id: str,
    end_zone_id: str,
    accessible_only: bool = False,
    avoid_congested: bool = True,
) -> RouteResponse:
    """Find optimal route between zones (GET variant for frontend use)."""
    from app.main import routing_engine

    result = routing_engine.find_route(
        origin=start_zone_id,
        destination=end_zone_id,
        accessible_only=accessible_only,
        avoid_congested=avoid_congested,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No route found from '{start_zone_id}' to '{end_zone_id}'",
        )

    return RouteResponse(**result)


@router.get(
    "/nearest/{zone_id}/{facility_type}",
    summary="Find nearest facility",
    description="Find the nearest facility of a given type from a zone.",
)
async def find_nearest(
    zone_id: str,
    facility_type: str,
    accessible: bool = False,
) -> dict:
    """Find nearest facility (restroom, exit, concession, etc.)."""
    from app.main import routing_engine, simulation_engine

    # Validate origin zone exists
    if not simulation_engine.get_zone(zone_id):
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found")

    result = routing_engine.find_nearest_facility(
        from_zone=zone_id,
        target_zone_type=facility_type,
        accessible_only=accessible,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No {facility_type} found accessible from '{zone_id}'",
        )

    return result
