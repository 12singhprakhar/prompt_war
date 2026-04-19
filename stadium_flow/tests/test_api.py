"""
Tests for API endpoints.

Validates HTTP responses, error handling, and data integrity
for all REST API endpoints. Uses the full lifespan context
to ensure services are initialized.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
async def client():
    """
    Provide an async HTTP test client with full lifespan.

    This ensures the simulation engine, agents, and all services
    are initialized before tests run.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Trigger lifespan startup by making a request
        yield ac


@pytest.fixture(autouse=True)
async def setup_services():
    """
    Ensure global services are initialized for API tests.

    Manually initializes the same services that the lifespan
    would create, since the test client doesn't trigger lifespan
    events with ASGITransport.
    """
    import app.main as main_module
    from app.services.simulation_engine import SimulationEngine
    from app.services.routing_engine import RoutingEngine
    from app.services.crowd_analytics import CrowdAnalytics
    from app.agents.base_agent import SharedMemory
    from app.agents.sentinel_agent import SentinelAgent
    from app.agents.concierge_agent import ConciergeAgent
    from app.agents.orchestra_agent import OrchestraAgent

    # Only initialize if not already initialized
    if main_module.simulation_engine is None:
        main_module.simulation_engine = SimulationEngine(
            initial_count=10000,
            max_capacity=132000,
            tick_interval=2.0,
        )
        main_module.routing_engine = RoutingEngine(main_module.simulation_engine.zones)
        main_module.crowd_analytics = CrowdAnalytics(main_module.simulation_engine.zones)
        main_module.simulation_engine.analytics_service = main_module.crowd_analytics

        memory = SharedMemory()
        main_module.shared_memory = memory
        main_module.sentinel_agent = SentinelAgent(
            memory=memory,
            zones=main_module.simulation_engine.zones,
            analytics=main_module.crowd_analytics,
        )
        main_module.concierge_agent = ConciergeAgent(
            memory=memory,
            zones=main_module.simulation_engine.zones,
            routing=main_module.routing_engine,
            analytics=main_module.crowd_analytics,
        )
        main_module.orchestra_agent = OrchestraAgent(
            memory=memory,
            zones=main_module.simulation_engine.zones,
        )

    yield

    # No teardown needed — services persist for the test session


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        """Health endpoint should return 200."""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_contains_status(self, client):
        """Health response should contain status field."""
        response = await client.get("/api/v1/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_contains_version(self, client):
        """Health response should contain version."""
        response = await client.get("/api/v1/health")
        data = response.json()
        assert "version" in data


class TestVenueEndpoints:
    """Tests for venue-related endpoints."""

    @pytest.mark.asyncio
    async def test_venue_info_returns_200(self, client):
        """Venue info endpoint should return 200."""
        response = await client.get("/api/v1/venues/info")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_venue_info_structure(self, client):
        """Venue info should contain expected fields."""
        response = await client.get("/api/v1/venues/info")
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "max_capacity" in data
        assert data["name"] == "Narendra Modi Stadium"

    @pytest.mark.asyncio
    async def test_venue_stats_returns_200(self, client):
        """Venue stats endpoint should return 200."""
        response = await client.get("/api/v1/venues/stats")
        assert response.status_code == 200


class TestZoneEndpoints:
    """Tests for zone-related endpoints."""

    @pytest.mark.asyncio
    async def test_list_zones_returns_200(self, client):
        """Zone list endpoint should return 200."""
        response = await client.get("/api/v1/zones/")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_zones_has_data(self, client):
        """Zone list should contain zones."""
        response = await client.get("/api/v1/zones/")
        data = response.json()
        assert "zones" in data
        assert "total" in data
        assert data["total"] > 0

    @pytest.mark.asyncio
    async def test_get_specific_zone(self, client):
        """Getting a specific zone should return its data."""
        response = await client.get("/api/v1/zones/block-a")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "block-a"
        assert data["name"] == "Block A"

    @pytest.mark.asyncio
    async def test_get_nonexistent_zone_returns_404(self, client):
        """Getting a non-existent zone should return 404."""
        response = await client.get("/api/v1/zones/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_heatmap_endpoint(self, client):
        """Heatmap endpoint should return data."""
        response = await client.get("/api/v1/zones/analytics/heatmap")
        assert response.status_code == 200
        data = response.json()
        assert "heatmap" in data

    @pytest.mark.asyncio
    async def test_recommendations_endpoint(self, client):
        """Recommendations endpoint should return data."""
        response = await client.get("/api/v1/zones/analytics/recommendations")
        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data


class TestRoutingEndpoints:
    """Tests for routing/navigation endpoints."""

    @pytest.mark.asyncio
    async def test_find_route(self, client):
        """Route finding should return a valid path."""
        response = await client.post(
            "/api/v1/routing/find",
            json={
                "origin_zone": "gate-1",
                "destination_zone": "concourse-north",
                "accessible_only": False,
                "avoid_congested": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "steps" in data
        assert len(data["steps"]) > 0

    @pytest.mark.asyncio
    async def test_find_route_invalid_zones(self, client):
        """Invalid zone IDs should return 404."""
        response = await client.post(
            "/api/v1/routing/find",
            json={
                "origin_zone": "nonexistent",
                "destination_zone": "gate-1",
            },
        )
        assert response.status_code == 404


class TestChatEndpoint:
    """Tests for the AI Concierge chat endpoint."""

    @pytest.mark.asyncio
    async def test_chat_returns_200(self, client):
        """Chat endpoint should return 200."""
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "Hello"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_returns_response(self, client):
        """Chat should return a non-empty response."""
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "Where are the restrooms?"},
        )
        data = response.json()
        assert "response" in data
        assert len(data["response"]) > 0

    @pytest.mark.asyncio
    async def test_chat_returns_session(self, client):
        """Chat should return a session ID."""
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "Hi there"},
        )
        data = response.json()
        assert "session_id" in data

    @pytest.mark.asyncio
    async def test_quick_actions(self, client):
        """Quick actions should be available."""
        response = await client.get("/api/v1/chat/quick-actions")
        assert response.status_code == 200
        data = response.json()
        assert "actions" in data
        assert len(data["actions"]) > 0
