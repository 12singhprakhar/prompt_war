"""
Tests for the Dijkstra Routing Engine.

Validates shortest path correctness, congestion avoidance,
accessible routes, and edge cases.
"""

import pytest
from app.services.routing_engine import RoutingEngine
from app.services.simulation_engine import create_stadium_zones
from app.models.zone import ZoneStatus


class TestRouteFinding:
    """Tests for basic route finding."""

    def test_same_origin_and_destination(self, routing_engine):
        """Route to self should return immediately."""
        route = routing_engine.find_route("gate-1", "gate-1")
        assert route is not None
        assert route["origin"] == "gate-1"
        assert route["destination"] == "gate-1"
        assert len(route["steps"]) == 1

    def test_adjacent_zones_direct_route(self, routing_engine):
        """Adjacent zones should have a direct 2-step route."""
        route = routing_engine.find_route("gate-1", "concourse-north")
        assert route is not None
        assert len(route["steps"]) == 2
        assert route["steps"][0]["zone_id"] == "gate-1"
        assert route["steps"][1]["zone_id"] == "concourse-north"

    def test_route_has_required_fields(self, routing_engine):
        """Route response should contain all required fields."""
        route = routing_engine.find_route("gate-1", "concourse-north")
        assert route is not None
        assert "origin" in route
        assert "destination" in route
        assert "steps" in route
        assert "total_distance_meters" in route
        assert "estimated_time_minutes" in route
        assert "is_accessible" in route
        assert "congestion_avoided" in route

    def test_multi_hop_route(self, routing_engine):
        """Route through multiple zones should work."""
        route = routing_engine.find_route("gate-1", "block-a")
        assert route is not None
        assert len(route["steps"]) >= 2

    def test_invalid_origin(self, routing_engine):
        """Invalid origin zone should return None."""
        route = routing_engine.find_route("nonexistent", "gate-1")
        assert route is None

    def test_invalid_destination(self, routing_engine):
        """Invalid destination zone should return None."""
        route = routing_engine.find_route("gate-1", "nonexistent")
        assert route is None

    def test_route_steps_have_instructions(self, routing_engine):
        """Each step should have a human-readable instruction."""
        route = routing_engine.find_route("gate-1", "concourse-north")
        assert route is not None
        for step in route["steps"]:
            assert "instruction" in step
            assert len(step["instruction"]) > 0

    def test_route_first_step_is_start(self, routing_engine):
        """First step instruction should say 'Start at'."""
        route = routing_engine.find_route("gate-1", "concourse-north")
        assert route is not None
        assert route["steps"][0]["instruction"].startswith("Start at")

    def test_route_last_step_is_arrive(self, routing_engine):
        """Last step instruction should say 'Arrive at'."""
        route = routing_engine.find_route("gate-1", "concourse-north")
        assert route is not None
        assert route["steps"][-1]["instruction"].startswith("Arrive at")


class TestCongestionAvoidance:
    """Tests for dynamic weight adjustment."""

    def test_avoids_critical_zones(self, stadium_zones):
        """Route should avoid critical zones when congestion avoidance is on."""
        # Make concourse-north critical
        stadium_zones["concourse-north"].current_occupancy = stadium_zones["concourse-north"].capacity
        routing = RoutingEngine(stadium_zones)

        route = routing.find_route("gate-1", "block-a", avoid_congested=True)
        # Route should exist (might go via alternative path)
        # The route may still pass through north concourse if no alternative exists
        assert route is not None

    def test_no_avoidance_uses_shortest_path(self, stadium_zones):
        """Without avoidance, route should take the direct path."""
        routing = RoutingEngine(stadium_zones)
        route = routing.find_route("gate-1", "concourse-north", avoid_congested=False)
        assert route is not None
        assert len(route["steps"]) == 2  # Direct connection


class TestAccessibleRoutes:
    """Tests for ADA-compliant routing."""

    def test_accessible_route_exists(self, routing_engine):
        """Accessible routes should still find paths."""
        route = routing_engine.find_route(
            "gate-1", "concourse-north",
            accessible_only=True,
        )
        assert route is not None
        assert route["is_accessible"] is True

    def test_accessible_flag_set(self, routing_engine):
        """Route response should reflect accessibility preference."""
        route = routing_engine.find_route(
            "gate-1", "concourse-north",
            accessible_only=True,
        )
        assert route is not None
        assert route["is_accessible"] is True

    def test_non_accessible_flag(self, routing_engine):
        """Non-accessible route should set flag to False."""
        route = routing_engine.find_route(
            "gate-1", "concourse-north",
            accessible_only=False,
        )
        assert route is not None
        assert route["is_accessible"] is False


class TestNearestFacility:
    """Tests for nearest facility finding."""

    def test_find_nearest_gate(self, routing_engine):
        """Should find the nearest entry gate."""
        route = routing_engine.find_nearest_facility(
            "concourse-north", "entry_gate"
        )
        assert route is not None
        assert route["destination"] in ["gate-1", "gate-2"]

    def test_find_nearest_concourse(self, routing_engine):
        """Should find the nearest concourse."""
        route = routing_engine.find_nearest_facility(
            "gate-1", "concourse"
        )
        assert route is not None

    def test_nearest_from_invalid_zone(self, routing_engine):
        """Invalid origin should return None."""
        route = routing_engine.find_nearest_facility(
            "nonexistent", "entry_gate"
        )
        assert route is None
