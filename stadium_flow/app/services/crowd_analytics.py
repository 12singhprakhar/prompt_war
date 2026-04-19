"""
Crowd Analytics Service.

Provides real-time crowd density analysis, wait time estimation,
and predictive flow modeling for venue optimization.
"""

import logging
import statistics
from datetime import datetime, timezone
from typing import Any, Optional

from app.models.zone import Zone, ZoneStatus, ZoneType

logger = logging.getLogger(__name__)


class CrowdAnalytics:
    """
    Analytical service for crowd intelligence.

    Computes heatmaps, wait time estimates, and congestion
    predictions from zone occupancy data.
    """

    def __init__(self, zones: dict[str, Zone]) -> None:
        self.zones = zones
        self._wait_time_cache: dict[str, float] = {}
        self._historical_ratios: dict[str, list[float]] = {}

    def compute_heatmap(self) -> list[dict[str, Any]]:
        """
        Generate a heatmap of crowd density across all zones.

        Returns:
            List of zone heatmap entries with position and intensity.
        """
        return [
            {
                "zone_id": zone.id,
                "name": zone.name,
                "x": zone.map_x,
                "y": zone.map_y,
                "intensity": round(zone.occupancy_ratio, 3),
                "status": zone.status.value,
                "occupancy": zone.current_occupancy,
                "capacity": zone.capacity,
            }
            for zone in self.zones.values()
        ]

    def estimate_wait_time(self, zone_id: str) -> float:
        """
        Estimate wait time for a zone in minutes.

        Uses a heuristic based on occupancy ratio:
        - < 50%: minimal wait (0-2 min)
        - 50-70%: moderate wait (2-5 min)
        - 70-85%: long wait (5-12 min)
        - > 85%: very long wait (12-20 min)

        Args:
            zone_id: The zone to estimate wait time for.

        Returns:
            Estimated wait time in minutes.
        """
        zone = self.zones.get(zone_id)
        if not zone:
            return 0.0

        ratio = zone.occupancy_ratio

        if ratio < 0.5:
            wait = ratio * 4.0
        elif ratio < 0.7:
            wait = 2.0 + (ratio - 0.5) * 15.0
        elif ratio < 0.85:
            wait = 5.0 + (ratio - 0.7) * 46.7
        else:
            wait = 12.0 + (ratio - 0.85) * 53.3

        self._wait_time_cache[zone_id] = round(wait, 1)
        return round(wait, 1)

    def get_congestion_summary(self) -> dict[str, Any]:
        """
        Get an aggregate congestion summary for the entire venue.

        Returns:
            Dictionary with zone counts per status level and stats.
        """
        status_counts = {s.value: 0 for s in ZoneStatus}
        occupancy_ratios = []

        for zone in self.zones.values():
            status_counts[zone.status.value] += 1
            occupancy_ratios.append(zone.occupancy_ratio)

        return {
            "status_distribution": status_counts,
            "average_occupancy_ratio": round(
                statistics.mean(occupancy_ratios), 3
            ) if occupancy_ratios else 0.0,
            "median_occupancy_ratio": round(
                statistics.median(occupancy_ratios), 3
            ) if occupancy_ratios else 0.0,
            "max_occupancy_ratio": round(
                max(occupancy_ratios), 3
            ) if occupancy_ratios else 0.0,
            "total_zones": len(self.zones),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def predict_congestion(self, zone_id: str) -> dict[str, Any]:
        """
        Predict future congestion for a zone based on recent trends.

        Tracks occupancy ratio history and projects forward
        using simple linear extrapolation.

        Args:
            zone_id: Zone to predict congestion for.

        Returns:
            Prediction dict with current, projected, and trend info.
        """
        zone = self.zones.get(zone_id)
        if not zone:
            return {"error": "Zone not found"}

        # Track history
        if zone_id not in self._historical_ratios:
            self._historical_ratios[zone_id] = []
        self._historical_ratios[zone_id].append(zone.occupancy_ratio)

        # Keep last 30 snapshots
        history = self._historical_ratios[zone_id][-30:]
        self._historical_ratios[zone_id] = history

        # Calculate trend
        if len(history) >= 3:
            recent_avg = statistics.mean(history[-3:])
            older_avg = statistics.mean(history[:3])
            trend = "increasing" if recent_avg > older_avg + 0.02 else (
                "decreasing" if recent_avg < older_avg - 0.02 else "stable"
            )
            projected = min(1.0, max(0.0, zone.occupancy_ratio + (recent_avg - older_avg)))
        else:
            trend = "insufficient_data"
            projected = zone.occupancy_ratio

        return {
            "zone_id": zone_id,
            "current_ratio": round(zone.occupancy_ratio, 3),
            "projected_ratio": round(projected, 3),
            "trend": trend,
            "data_points": len(history),
            "estimated_wait_minutes": self.estimate_wait_time(zone_id),
        }

    def get_recommendations(self) -> list[dict[str, str]]:
        """
        Generate actionable recommendations based on current state.

        Returns:
            List of recommendation dicts with type, message, and priority.
        """
        recommendations = []

        # Find critical zones
        critical = [z for z in self.zones.values() if z.status == ZoneStatus.CRITICAL]
        for zone in critical:
            recommendations.append({
                "type": "congestion",
                "priority": "high",
                "zone_id": zone.id,
                "message": (
                    f"{zone.name} is at {zone.occupancy_ratio:.0%} capacity. "
                    f"Recommend redirecting traffic via adjacent zones."
                ),
            })

        # Find underutilized zones adjacent to busy ones
        busy = [z for z in self.zones.values() if z.status == ZoneStatus.BUSY]
        for zone in busy:
            for adj_id in zone.adjacent_zones:
                adj = self.zones.get(adj_id)
                if adj and adj.status == ZoneStatus.CLEAR:
                    recommendations.append({
                        "type": "redistribution",
                        "priority": "medium",
                        "zone_id": zone.id,
                        "message": (
                            f"Redirect overflow from {zone.name} to "
                            f"{adj.name} (currently {adj.occupancy_ratio:.0%} full)."
                        ),
                    })

        return recommendations
