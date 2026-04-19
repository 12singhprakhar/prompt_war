"""
Sentinel Agent — Crowd Intelligence.

Monitors crowd density across all zones in real-time, detects
capacity threshold breaches, and publishes alerts to the shared
memory bus for inter-agent coordination.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from app.agents.base_agent import BaseAgent, SharedMemory
from app.models.event import Event, EventSeverity, EventType
from app.models.zone import Zone, ZoneStatus
from app.services.crowd_analytics import CrowdAnalytics
from app.database.repository import EventRepository, AnalyticsRepository


class SentinelAgent(BaseAgent):
    """
    Crowd intelligence agent that monitors zone occupancy.

    Responsibilities:
    - Continuously scan all zones for capacity breaches
    - Generate alerts when congestion exceeds thresholds
    - Log analytics snapshots for historical analysis
    - Publish crowd intelligence to shared memory for other agents
    """

    def __init__(
        self,
        memory: SharedMemory,
        zones: dict[str, Zone],
        analytics: CrowdAnalytics,
        congestion_threshold: float = 0.85,
    ) -> None:
        super().__init__(
            name="Sentinel Agent",
            agent_id="sentinel",
            memory=memory,
        )
        self.zones = zones
        self.analytics = analytics
        self.congestion_threshold = congestion_threshold
        self.event_repo = EventRepository()
        self.analytics_repo = AnalyticsRepository()

        # Track which zones already have active alerts to avoid duplicates
        self._active_alerts: set[str] = set()

    async def perceive(self) -> dict[str, Any]:
        """
        Scan all zones and gather occupancy data.

        Returns:
            Dictionary with zone states and congestion summary.
        """
        zone_states = {}
        critical_zones = []
        busy_zones = []

        for zone_id, zone in self.zones.items():
            state = {
                "id": zone_id,
                "name": zone.name,
                "occupancy_ratio": zone.occupancy_ratio,
                "status": zone.status.value,
                "current": zone.current_occupancy,
                "capacity": zone.capacity,
            }
            zone_states[zone_id] = state

            if zone.status == ZoneStatus.CRITICAL:
                critical_zones.append(zone_id)
            elif zone.status == ZoneStatus.BUSY:
                busy_zones.append(zone_id)

        congestion_summary = self.analytics.get_congestion_summary()

        return {
            "zones": zone_states,
            "critical_zones": critical_zones,
            "busy_zones": busy_zones,
            "congestion_summary": congestion_summary,
        }

    async def decide(self, perception: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Analyze crowd data and determine alert actions.

        Generates alerts for newly critical zones and resolves
        alerts for zones that have returned to normal.
        """
        actions = []

        # Check for new critical zones
        for zone_id in perception["critical_zones"]:
            if zone_id not in self._active_alerts:
                zone = self.zones[zone_id]
                actions.append({
                    "type": "create_alert",
                    "zone_id": zone_id,
                    "severity": EventSeverity.CRITICAL,
                    "message": (
                        f"⚠️ {zone.name} has reached {zone.occupancy_ratio:.0%} "
                        f"capacity ({zone.current_occupancy}/{zone.capacity}). "
                        f"Recommend redirecting incoming traffic."
                    ),
                })

        # Check for busy zones approaching threshold
        for zone_id in perception["busy_zones"]:
            if zone_id not in self._active_alerts:
                zone = self.zones[zone_id]
                if zone.occupancy_ratio > 0.80:  # Pre-warning at 80%
                    actions.append({
                        "type": "create_alert",
                        "zone_id": zone_id,
                        "severity": EventSeverity.WARNING,
                        "message": (
                            f"📊 {zone.name} is approaching capacity at "
                            f"{zone.occupancy_ratio:.0%}. Monitor closely."
                        ),
                    })

        # Resolve alerts for zones that improved
        for zone_id in list(self._active_alerts):
            zone = self.zones.get(zone_id)
            if zone and zone.status in (ZoneStatus.CLEAR, ZoneStatus.MODERATE):
                actions.append({
                    "type": "resolve_alert",
                    "zone_id": zone_id,
                })

        # Always log analytics snapshot
        actions.append({"type": "log_analytics"})

        return actions

    async def act(self, actions: list[dict[str, Any]]) -> None:
        """Execute alert creation, resolution, and analytics logging."""
        for action in actions:
            if action["type"] == "create_alert":
                await self._create_alert(action)

            elif action["type"] == "resolve_alert":
                self._active_alerts.discard(action["zone_id"])
                self.logger.info("Resolved alert for zone: %s", action["zone_id"])

            elif action["type"] == "log_analytics":
                await self._log_analytics()

        # Publish current intelligence to shared memory
        recommendations = self.analytics.get_recommendations()
        await self.memory.publish(
            "crowd.intelligence",
            {
                "active_alerts": list(self._active_alerts),
                "recommendations": recommendations,
                "total_zones_monitored": len(self.zones),
            },
            source=self.agent_id,
        )

    async def _create_alert(self, action: dict) -> None:
        """Create and persist a new crowd alert event."""
        zone_id = action["zone_id"]
        self._active_alerts.add(zone_id)

        event = Event(
            id=f"evt-{uuid.uuid4().hex[:8]}",
            event_type=EventType.CROWD_ALERT,
            severity=action["severity"],
            source_agent=self.agent_id,
            title=f"Crowd Alert: {self.zones[zone_id].name}",
            message=action["message"],
            zone_id=zone_id,
            metadata={
                "occupancy_ratio": self.zones[zone_id].occupancy_ratio,
                "current_occupancy": self.zones[zone_id].current_occupancy,
                "capacity": self.zones[zone_id].capacity,
            },
        )

        try:
            await self.event_repo.save_event(event)
        except Exception as e:
            self.logger.error("Failed to save event: %s", e)

        # Publish to shared memory for other agents
        await self.memory.publish(
            "crowd.alert",
            event.to_dict(),
            source=self.agent_id,
        )

        self.logger.warning(
            "ALERT: %s — %s", event.title, action["message"]
        )

    async def _log_analytics(self) -> None:
        """Log zone snapshots for time-series analytics."""
        for zone_id, zone in self.zones.items():
            try:
                await self.analytics_repo.log_zone_snapshot(
                    zone_id=zone_id,
                    occupancy=zone.current_occupancy,
                    capacity=zone.capacity,
                    status=zone.status.value,
                )
            except Exception as e:
                self.logger.debug("Analytics log error: %s", e)
