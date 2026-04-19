"""
Orchestra Agent — Staff Coordination.

Coordinates venue staff deployment based on crowd intelligence
from the Sentinel and Concierge agents. Manages emergency
protocols and dispatches resources to high-need areas.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from app.agents.base_agent import BaseAgent, SharedMemory
from app.models.event import Event, EventSeverity, EventType
from app.models.zone import Zone, ZoneStatus
from app.database.repository import EventRepository
from app.services.google_services import BigQueryService


class OrchestraAgent(BaseAgent):
    """
    Staff coordination and resource dispatch agent.

    Responsibilities:
    - Subscribe to crowd alerts from SentinelAgent
    - Coordinate staff deployment to congested zones
    - Manage emergency evacuation protocols
    - Log all decisions for compliance and audit
    - Sync analytics to BigQuery for reporting
    """

    def __init__(
        self,
        memory: SharedMemory,
        zones: dict[str, Zone],
    ) -> None:
        super().__init__(
            name="Orchestra Agent",
            agent_id="orchestra",
            memory=memory,
        )
        self.zones = zones
        self.event_repo = EventRepository()
        self.bigquery = BigQueryService()

        # Staff deployment tracking
        self._deployed_staff: dict[str, int] = {}
        self._pending_dispatches: list[dict] = []
        self._resolved_incidents: int = 0

        # Subscribe to crowd alerts
        self._setup_subscriptions()

    def _setup_subscriptions(self) -> None:
        """Register handlers for shared memory events."""
        # Note: Subscriptions are set up when the agent starts
        pass

    async def start(self, interval: float = 5.0) -> None:
        """Start with crowd alert subscription."""
        # Subscribe to SentinelAgent alerts
        await self.memory.subscribe("crowd.alert", self._on_crowd_alert)
        await super().start(interval)

    async def _on_crowd_alert(self, alert_data: dict) -> None:
        """
        Handle incoming crowd alerts from SentinelAgent.

        Adds the alert to the pending dispatch queue for
        processing in the next decision cycle.
        """
        self.logger.info(
            "Received crowd alert: %s (severity: %s)",
            alert_data.get("title", "Unknown"),
            alert_data.get("severity", "unknown"),
        )
        self._pending_dispatches.append({
            "type": "crowd_response",
            "alert": alert_data,
            "received_at": datetime.now(timezone.utc).isoformat(),
        })

    async def perceive(self) -> dict[str, Any]:
        """
        Gather information about current staff deployment and venue state.
        """
        # Get crowd intelligence from shared memory
        crowd_intel = await self.memory.get("crowd.intelligence") or {}

        # Analyze zone statuses
        zone_statuses = {}
        for zone_id, zone in self.zones.items():
            zone_statuses[zone_id] = {
                "status": zone.status.value,
                "occupancy_ratio": zone.occupancy_ratio,
                "needs_staff": zone.status in (ZoneStatus.CRITICAL, ZoneStatus.BUSY),
            }

        return {
            "crowd_intelligence": crowd_intel,
            "zone_statuses": zone_statuses,
            "pending_dispatches": list(self._pending_dispatches),
            "deployed_staff": dict(self._deployed_staff),
            "total_resolved": self._resolved_incidents,
        }

    async def decide(self, perception: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Determine staff deployment actions based on current state.

        Decision logic:
        1. Process any pending crowd alerts
        2. Identify zones needing additional staff
        3. Identify zones where staff can be reassigned
        4. Generate dispatch/recall orders
        """
        actions = []

        # Process pending dispatches
        for dispatch in perception["pending_dispatches"]:
            alert = dispatch.get("alert", {})
            zone_id = alert.get("zone_id")

            if zone_id and zone_id not in self._deployed_staff:
                severity = alert.get("severity", "warning")
                staff_count = 2 if severity == "critical" else 1

                actions.append({
                    "type": "deploy_staff",
                    "zone_id": zone_id,
                    "staff_count": staff_count,
                    "reason": alert.get("message", "Crowd alert"),
                    "severity": severity,
                })

        # Check if any deployed staff can be recalled
        for zone_id, count in list(self._deployed_staff.items()):
            zone = self.zones.get(zone_id)
            if zone and zone.status in (ZoneStatus.CLEAR, ZoneStatus.MODERATE):
                actions.append({
                    "type": "recall_staff",
                    "zone_id": zone_id,
                    "staff_count": count,
                })

        # Proactive: deploy to zones approaching critical
        for zone_id, status in perception["zone_statuses"].items():
            if (
                status["needs_staff"]
                and zone_id not in self._deployed_staff
                and status["occupancy_ratio"] > 0.82
            ):
                actions.append({
                    "type": "deploy_staff",
                    "zone_id": zone_id,
                    "staff_count": 1,
                    "reason": f"Proactive deployment — {status['occupancy_ratio']:.0%} capacity",
                    "severity": "warning",
                })

        # Log analytics to BigQuery
        if self.cycle_count % 5 == 0:  # Every 5th cycle
            actions.append({"type": "sync_analytics"})

        return actions

    async def act(self, actions: list[dict[str, Any]]) -> None:
        """Execute staff deployment, recall, and analytics sync actions."""
        for action in actions:
            if action["type"] == "deploy_staff":
                await self._deploy_staff(action)

            elif action["type"] == "recall_staff":
                await self._recall_staff(action)

            elif action["type"] == "sync_analytics":
                await self._sync_analytics()

        # Clear processed dispatches
        self._pending_dispatches.clear()

        # Publish staff deployment state
        await self.memory.publish(
            "staff.deployment",
            {
                "deployed": dict(self._deployed_staff),
                "total_deployed": sum(self._deployed_staff.values()),
                "incidents_resolved": self._resolved_incidents,
            },
            source=self.agent_id,
        )

    async def _deploy_staff(self, action: dict) -> None:
        """Deploy staff to a zone and log the decision."""
        zone_id = action["zone_id"]
        staff_count = action["staff_count"]

        self._deployed_staff[zone_id] = (
            self._deployed_staff.get(zone_id, 0) + staff_count
        )

        # Create dispatch event
        event = Event(
            id=f"dispatch-{uuid.uuid4().hex[:8]}",
            event_type=EventType.STAFF_DISPATCH,
            severity=EventSeverity(action.get("severity", "warning")),
            source_agent=self.agent_id,
            title=f"Staff Deployed: {self.zones.get(zone_id, zone_id)}",
            message=(
                f"Deployed {staff_count} staff to "
                f"{self.zones[zone_id].name if zone_id in self.zones else zone_id}. "
                f"Reason: {action.get('reason', 'N/A')}"
            ),
            zone_id=zone_id,
            metadata={"staff_count": staff_count},
        )

        try:
            await self.event_repo.save_event(event)
        except Exception as e:
            self.logger.error("Failed to log dispatch: %s", e)

        # Publish to shared memory
        await self.memory.publish(
            "staff.dispatch",
            event.to_dict(),
            source=self.agent_id,
        )

        self.logger.info(
            "DISPATCH: %d staff → %s (%s)",
            staff_count,
            self.zones[zone_id].name if zone_id in self.zones else zone_id,
            action.get("reason", ""),
        )

    async def _recall_staff(self, action: dict) -> None:
        """Recall staff from a zone that has improved."""
        zone_id = action["zone_id"]
        if zone_id in self._deployed_staff:
            del self._deployed_staff[zone_id]
            self._resolved_incidents += 1
            self.logger.info(
                "RECALL: Staff recalled from %s (resolved)",
                self.zones[zone_id].name if zone_id in self.zones else zone_id,
            )

    async def _sync_analytics(self) -> None:
        """Sync current state to BigQuery for analytics."""
        for zone_id, zone in self.zones.items():
            await self.bigquery.log_event({
                "zone_id": zone_id,
                "occupancy": zone.current_occupancy,
                "capacity": zone.capacity,
                "status": zone.status.value,
                "staff_deployed": self._deployed_staff.get(zone_id, 0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        await self.bigquery.flush()
        self.logger.debug("Analytics synced to BigQuery")

    def get_deployment_summary(self) -> dict:
        """Get current staff deployment summary."""
        return {
            "deployments": [
                {
                    "zone_id": zone_id,
                    "zone_name": self.zones[zone_id].name if zone_id in self.zones else zone_id,
                    "staff_count": count,
                    "zone_status": self.zones[zone_id].status.value if zone_id in self.zones else "unknown",
                }
                for zone_id, count in self._deployed_staff.items()
            ],
            "total_deployed": sum(self._deployed_staff.values()),
            "incidents_resolved": self._resolved_incidents,
        }
