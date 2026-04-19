"""
Tests for the Multi-Agent System.

Validates agent lifecycle, inter-agent communication via
shared memory, and decision-making logic.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.base_agent import SharedMemory, BaseAgent
from app.agents.sentinel_agent import SentinelAgent
from app.agents.concierge_agent import ConciergeAgent
from app.agents.orchestra_agent import OrchestraAgent
from app.models.zone import ZoneStatus
from app.services.simulation_engine import create_stadium_zones
from app.services.crowd_analytics import CrowdAnalytics
from app.services.routing_engine import RoutingEngine


class TestSharedMemory:
    """Tests for the inter-agent shared memory bus."""

    @pytest.mark.asyncio
    async def test_publish_and_get(self, shared_memory):
        """Published data should be retrievable."""
        await shared_memory.publish("test.topic", {"value": 42}, source="test")
        result = await shared_memory.get("test.topic")
        assert result == {"value": 42}

    @pytest.mark.asyncio
    async def test_subscribe_receives_events(self, shared_memory):
        """Subscribers should receive published events."""
        received = []

        async def handler(data):
            received.append(data)

        await shared_memory.subscribe("test.events", handler)
        await shared_memory.publish("test.events", {"alert": True})

        assert len(received) == 1
        assert received[0] == {"alert": True}

    @pytest.mark.asyncio
    async def test_get_nonexistent_topic(self, shared_memory):
        """Getting a non-existent topic should return None."""
        result = await shared_memory.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_event_log_bounded(self, shared_memory):
        """Event log should be bounded to prevent memory leaks."""
        for i in range(600):
            await shared_memory.publish(f"topic.{i}", {"i": i})

        events = await shared_memory.get_recent_events(limit=1000)
        assert len(events) <= 500

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, shared_memory):
        """Multiple subscribers on same topic should all receive."""
        received_a = []
        received_b = []

        async def handler_a(data): received_a.append(data)
        async def handler_b(data): received_b.append(data)

        await shared_memory.subscribe("multi", handler_a)
        await shared_memory.subscribe("multi", handler_b)
        await shared_memory.publish("multi", {"msg": "hello"})

        assert len(received_a) == 1
        assert len(received_b) == 1


class TestSentinelAgent:
    """Tests for the Sentinel (crowd intelligence) agent."""

    @pytest.mark.asyncio
    async def test_perceive_returns_zone_data(self):
        """Perceive should return zone status data."""
        zones = create_stadium_zones()
        analytics = CrowdAnalytics(zones)
        memory = SharedMemory()
        agent = SentinelAgent(memory, zones, analytics)

        perception = await agent.perceive()
        assert "zones" in perception
        assert "critical_zones" in perception
        assert "busy_zones" in perception
        assert "congestion_summary" in perception

    @pytest.mark.asyncio
    async def test_detects_critical_zone(self):
        """Agent should detect zones exceeding capacity threshold."""
        zones = create_stadium_zones()
        # Set a zone to critical
        zones["block-a"].current_occupancy = int(zones["block-a"].capacity * 0.95)
        analytics = CrowdAnalytics(zones)
        memory = SharedMemory()
        agent = SentinelAgent(memory, zones, analytics)

        perception = await agent.perceive()
        assert "block-a" in perception["critical_zones"]

        actions = await agent.decide(perception)
        alert_actions = [a for a in actions if a["type"] == "create_alert"]
        assert len(alert_actions) > 0

    @pytest.mark.asyncio
    async def test_no_duplicate_alerts(self):
        """Agent should not create duplicate alerts for the same zone."""
        zones = create_stadium_zones()
        zones["block-a"].current_occupancy = int(zones["block-a"].capacity * 0.95)
        analytics = CrowdAnalytics(zones)
        memory = SharedMemory()
        agent = SentinelAgent(memory, zones, analytics)

        # First cycle — should create alert
        p1 = await agent.perceive()
        a1 = await agent.decide(p1)
        await agent.act(a1)

        # Second cycle — should NOT create duplicate
        p2 = await agent.perceive()
        a2 = await agent.decide(p2)
        create_alerts = [a for a in a2 if a["type"] == "create_alert" and a["zone_id"] == "block-a"]
        assert len(create_alerts) == 0

    @pytest.mark.asyncio
    async def test_resolves_cleared_alerts(self):
        """Agent should resolve alerts when zones improve."""
        zones = create_stadium_zones()
        zones["block-a"].current_occupancy = int(zones["block-a"].capacity * 0.95)
        analytics = CrowdAnalytics(zones)
        memory = SharedMemory()
        agent = SentinelAgent(memory, zones, analytics)

        # Create alert
        p1 = await agent.perceive()
        a1 = await agent.decide(p1)
        await agent.act(a1)

        # Clear the zone
        zones["block-a"].current_occupancy = int(zones["block-a"].capacity * 0.3)

        p2 = await agent.perceive()
        a2 = await agent.decide(p2)
        resolve_actions = [a for a in a2 if a["type"] == "resolve_alert"]
        assert len(resolve_actions) > 0


class TestConciergeAgent:
    """Tests for the Concierge (fan assistant) agent."""

    @pytest.mark.asyncio
    async def test_handle_chat_returns_response(self):
        """Chat handler should return a response dict."""
        zones = create_stadium_zones()
        analytics = CrowdAnalytics(zones)
        routing = RoutingEngine(zones)
        memory = SharedMemory()
        agent = ConciergeAgent(memory, zones, routing, analytics)

        result = await agent.handle_chat("Where is the nearest restroom?")

        assert "response" in result
        assert "session_id" in result
        assert "timestamp" in result
        assert len(result["response"]) > 0

    @pytest.mark.asyncio
    async def test_session_continuity(self):
        """Session ID should persist across messages."""
        zones = create_stadium_zones()
        analytics = CrowdAnalytics(zones)
        routing = RoutingEngine(zones)
        memory = SharedMemory()
        agent = ConciergeAgent(memory, zones, routing, analytics)

        result1 = await agent.handle_chat("Hello")
        session = result1["session_id"]

        result2 = await agent.handle_chat("Where is food?", session_id=session)
        assert result2["session_id"] == session

    @pytest.mark.asyncio
    async def test_quick_actions_available(self):
        """Quick actions should be pre-defined."""
        zones = create_stadium_zones()
        analytics = CrowdAnalytics(zones)
        routing = RoutingEngine(zones)
        memory = SharedMemory()
        agent = ConciergeAgent(memory, zones, routing, analytics)

        actions = await agent.get_quick_actions()
        assert len(actions) >= 5
        assert all("id" in a and "label" in a and "prompt" in a for a in actions)

    @pytest.mark.asyncio
    async def test_restroom_query_response(self):
        """Query about restrooms should contain relevant info."""
        zones = create_stadium_zones()
        analytics = CrowdAnalytics(zones)
        routing = RoutingEngine(zones)
        memory = SharedMemory()
        agent = ConciergeAgent(memory, zones, routing, analytics)

        result = await agent.handle_chat("Where are the restrooms?")
        response = result["response"].lower()
        assert any(w in response for w in ["restroom", "concourse", "bathroom"])


class TestOrchestraAgent:
    """Tests for the Orchestra (staff coordination) agent."""

    @pytest.mark.asyncio
    async def test_perceive_returns_state(self):
        """Perceive should return deployment and zone data."""
        zones = create_stadium_zones()
        memory = SharedMemory()
        agent = OrchestraAgent(memory, zones)

        perception = await agent.perceive()
        assert "zone_statuses" in perception
        assert "pending_dispatches" in perception
        assert "deployed_staff" in perception

    @pytest.mark.asyncio
    async def test_deployment_summary(self):
        """Agent should provide deployment summary."""
        zones = create_stadium_zones()
        memory = SharedMemory()
        agent = OrchestraAgent(memory, zones)

        summary = agent.get_deployment_summary()
        assert "deployments" in summary
        assert "total_deployed" in summary
        assert "incidents_resolved" in summary
