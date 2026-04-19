"""
Dijkstra Routing Engine.

Provides optimal pathfinding through the venue graph with
dynamic congestion-aware weight adjustment and accessible
route alternatives.
"""

import heapq
import logging
from typing import Optional

from app.models.zone import Zone, ZoneStatus

logger = logging.getLogger(__name__)


class RoutingEngine:
    """
    Graph-based routing engine using Dijkstra's algorithm.

    Builds a weighted graph from the venue zone topology and
    computes shortest paths with optional congestion avoidance
    and accessibility constraints.
    """

    # Base traversal times in seconds between zone types
    BASE_WEIGHTS = {
        "entry_gate": 30,
        "concourse": 60,
        "seating": 45,
        "vip": 40,
        "hospitality": 50,
        "field_level": 35,
    }

    # Congestion multipliers applied to base weights
    CONGESTION_MULTIPLIERS = {
        ZoneStatus.CLEAR: 1.0,
        ZoneStatus.MODERATE: 1.3,
        ZoneStatus.BUSY: 1.8,
        ZoneStatus.CRITICAL: 3.0,
        ZoneStatus.CLOSED: float("inf"),
    }

    def __init__(self, zones: dict[str, Zone]) -> None:
        self.zones = zones

    def find_route(
        self,
        origin: str,
        destination: str,
        accessible_only: bool = False,
        avoid_congested: bool = True,
    ) -> Optional[dict]:
        """
        Find the optimal route between two zones.

        Uses Dijkstra's algorithm with dynamic weights based on
        current congestion levels.

        Args:
            origin: Starting zone ID.
            destination: Target zone ID.
            accessible_only: If True, exclude non-accessible zones.
            avoid_congested: If True, penalize congested zones.

        Returns:
            Route dictionary with steps, distance, and time estimates,
            or None if no path exists.
        """
        if origin not in self.zones or destination not in self.zones:
            logger.warning("Invalid zone IDs: %s → %s", origin, destination)
            return None

        if origin == destination:
            return self._build_route_response(
                origin, destination, [origin], 0, accessible_only, avoid_congested
            )

        # Dijkstra's algorithm
        distances: dict[str, float] = {zone_id: float("inf") for zone_id in self.zones}
        distances[origin] = 0
        previous: dict[str, Optional[str]] = {zone_id: None for zone_id in self.zones}
        visited: set[str] = set()

        # Priority queue: (distance, zone_id)
        pq: list[tuple[float, str]] = [(0, origin)]

        while pq:
            current_dist, current_id = heapq.heappop(pq)

            if current_id in visited:
                continue
            visited.add(current_id)

            if current_id == destination:
                break

            current_zone = self.zones[current_id]

            for neighbor_id in current_zone.adjacent_zones:
                if neighbor_id not in self.zones or neighbor_id in visited:
                    continue

                neighbor = self.zones[neighbor_id]

                # Skip non-accessible zones when requested
                if accessible_only and not neighbor.is_accessible:
                    continue

                # Calculate edge weight
                weight = self._calculate_weight(neighbor, avoid_congested)

                if weight == float("inf"):
                    continue  # Zone is blocked

                new_dist = current_dist + weight
                if new_dist < distances[neighbor_id]:
                    distances[neighbor_id] = new_dist
                    previous[neighbor_id] = current_id
                    heapq.heappush(pq, (new_dist, neighbor_id))

        # Reconstruct path
        if distances[destination] == float("inf"):
            logger.warning("No path found: %s → %s", origin, destination)
            return None

        path = self._reconstruct_path(previous, destination)
        return self._build_route_response(
            origin, destination, path,
            distances[destination],
            accessible_only, avoid_congested,
        )

    def _calculate_weight(self, zone: Zone, avoid_congested: bool) -> float:
        """
        Calculate traversal weight for a zone.

        Weight = base_time × congestion_multiplier
        """
        base = self.BASE_WEIGHTS.get(zone.zone_type.value, 60)

        if avoid_congested:
            multiplier = self.CONGESTION_MULTIPLIERS.get(zone.status, 1.0)
        else:
            multiplier = 1.0

        return base * multiplier

    def _reconstruct_path(
        self, previous: dict[str, Optional[str]], destination: str
    ) -> list[str]:
        """Reconstruct the path from Dijkstra's previous map."""
        path = []
        current: Optional[str] = destination
        while current is not None:
            path.append(current)
            current = previous.get(current)
        path.reverse()
        return path

    def _build_route_response(
        self,
        origin: str,
        destination: str,
        path: list[str],
        total_weight: float,
        accessible_only: bool,
        avoid_congested: bool,
    ) -> dict:
        """Build a structured route response."""
        steps = []
        for i, zone_id in enumerate(path):
            zone = self.zones[zone_id]
            if i == 0:
                instruction = f"Start at {zone.name}"
            elif i == len(path) - 1:
                instruction = f"Arrive at {zone.name}"
            else:
                instruction = f"Continue through {zone.name}"

            steps.append({
                "zone_id": zone_id,
                "zone_name": zone.name,
                "instruction": instruction,
                "distance_meters": round(
                    self.BASE_WEIGHTS.get(zone.zone_type.value, 60) * 0.8, 1
                ),
                "congestion_status": zone.status.value,
            })

        total_distance = sum(s["distance_meters"] for s in steps)
        # Estimate 1 meter per second walking speed
        estimated_minutes = round(total_weight / 60, 1)

        return {
            "origin": origin,
            "destination": destination,
            "steps": steps,
            "total_distance_meters": round(total_distance, 1),
            "estimated_time_minutes": max(estimated_minutes, 0.5),
            "is_accessible": accessible_only,
            "congestion_avoided": avoid_congested,
            "alternative_available": len(path) > 2,
        }

    def find_nearest_facility(
        self,
        from_zone: str,
        target_zone_type: str,
        accessible_only: bool = False,
    ) -> Optional[dict]:
        """
        Find the nearest zone of a specific type.

        Useful for "nearest restroom" or "nearest exit" queries.

        Args:
            from_zone: Starting zone ID.
            target_zone_type: Zone type to search for.
            accessible_only: Only consider accessible zones.

        Returns:
            Route to nearest matching zone, or None.
        """
        candidates = [
            z for z in self.zones.values()
            if z.zone_type.value == target_zone_type
            and z.is_active
            and (not accessible_only or z.is_accessible)
        ]

        best_route = None
        best_time = float("inf")

        for candidate in candidates:
            route = self.find_route(
                from_zone, candidate.id, accessible_only, avoid_congested=True
            )
            if route and route["estimated_time_minutes"] < best_time:
                best_time = route["estimated_time_minutes"]
                best_route = route

        return best_route
