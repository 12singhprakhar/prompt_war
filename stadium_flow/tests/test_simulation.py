"""
Tests for the Crowd Simulation Engine.

Validates crowd distribution, movement patterns, and zone
capacity enforcement across different scenarios.
"""

import pytest
from app.services.simulation_engine import SimulationEngine, create_stadium_zones
from app.models.zone import ZoneType, ZoneStatus


class TestStadiumTopology:
    """Tests for the stadium zone creation."""

    def test_creates_all_seating_blocks(self):
        """Verify all 18 seating blocks (A-R) are created."""
        zones = create_stadium_zones()
        seating = [z for z in zones.values() if z.zone_type == ZoneType.SEATING]
        assert len(seating) == 18

    def test_creates_entry_gates(self):
        """Verify all 6 entry gates exist."""
        zones = create_stadium_zones()
        gates = [z for z in zones.values() if z.zone_type == ZoneType.ENTRY_GATE]
        assert len(gates) == 6

    def test_creates_concourses(self):
        """Verify 4 concourse zones exist (N/S/E/W)."""
        zones = create_stadium_zones()
        concourses = [z for z in zones.values() if z.zone_type == ZoneType.CONCOURSE]
        assert len(concourses) == 4

    def test_creates_vip_zones(self):
        """Verify VIP and hospitality zones exist."""
        zones = create_stadium_zones()
        assert "presidential-suite" in zones
        assert "premium-gallery" in zones

    def test_total_capacity_near_expected(self):
        """Total seating capacity should approximate 132,000."""
        zones = create_stadium_zones()
        total = sum(z.capacity for z in zones.values())
        assert total > 100000  # Including all zone types

    def test_all_zones_have_adjacency(self):
        """Every zone should have at least one adjacent zone."""
        zones = create_stadium_zones()
        for zone_id, zone in zones.items():
            assert len(zone.adjacent_zones) > 0, f"{zone_id} has no adjacent zones"

    def test_adjacency_links_are_valid(self):
        """All adjacent zone references should point to existing zones."""
        zones = create_stadium_zones()
        for zone_id, zone in zones.items():
            for adj_id in zone.adjacent_zones:
                assert adj_id in zones, f"{zone_id} references non-existent zone: {adj_id}"


class TestSimulationEngine:
    """Tests for the simulation engine behavior."""

    def test_initial_distribution(self):
        """Initial crowd should be distributed across seating zones."""
        engine = SimulationEngine(initial_count=10000, max_capacity=132000)
        total = sum(z.current_occupancy for z in engine.zones.values())
        assert total == 10000

    def test_initial_distribution_in_seating(self):
        """Initial crowd should primarily be in seating zones."""
        engine = SimulationEngine(initial_count=30000, max_capacity=132000)
        seating = sum(
            z.current_occupancy for z in engine.zones.values()
            if z.zone_type == ZoneType.SEATING
        )
        assert seating == 30000  # All initial crowd in seating

    def test_no_zone_exceeds_capacity(self):
        """No zone should exceed its capacity after initialization."""
        engine = SimulationEngine(initial_count=50000, max_capacity=132000)
        for zone in engine.zones.values():
            assert zone.current_occupancy <= zone.capacity, (
                f"{zone.name} exceeds capacity: {zone.current_occupancy}/{zone.capacity}"
            )

    def test_state_contains_required_fields(self):
        """get_state() should return properly structured data."""
        engine = SimulationEngine(initial_count=5000)
        state = engine.get_state()

        assert "tick" in state
        assert "timestamp" in state
        assert "zones" in state
        assert "metrics" in state

        metrics = state["metrics"]
        assert "total_attendees" in metrics
        assert "max_capacity" in metrics
        assert "occupancy_percentage" in metrics
        assert "peak_occupancy" in metrics
        assert "critical_zones" in metrics

    def test_get_zone_returns_valid_zone(self):
        """get_zone() should return the correct zone."""
        engine = SimulationEngine(initial_count=5000)
        zone = engine.get_zone("block-a")
        assert zone is not None
        assert zone.name == "Block A"

    def test_get_zone_returns_none_for_invalid(self):
        """get_zone() should return None for unknown zone IDs."""
        engine = SimulationEngine(initial_count=5000)
        assert engine.get_zone("nonexistent") is None

    def test_get_all_zones_count(self):
        """get_all_zones() should return all zones."""
        engine = SimulationEngine(initial_count=5000)
        zones = engine.get_all_zones()
        assert len(zones) >= 28  # 18 blocks + 4 concourses + 6 gates + 2 VIP

    def test_zero_initial_count(self):
        """Engine should handle zero initial attendees."""
        engine = SimulationEngine(initial_count=0, max_capacity=132000)
        total = sum(z.current_occupancy for z in engine.zones.values())
        assert total == 0


class TestZoneStatus:
    """Tests for zone status computation."""

    def test_clear_status(self):
        """Zone below 50% should be CLEAR."""
        zones = create_stadium_zones()
        zone = zones["block-a"]
        zone.current_occupancy = int(zone.capacity * 0.3)
        assert zone.status == ZoneStatus.CLEAR

    def test_moderate_status(self):
        """Zone between 50-70% should be MODERATE."""
        zones = create_stadium_zones()
        zone = zones["block-a"]
        zone.current_occupancy = int(zone.capacity * 0.6)
        assert zone.status == ZoneStatus.MODERATE

    def test_busy_status(self):
        """Zone between 70-85% should be BUSY."""
        zones = create_stadium_zones()
        zone = zones["block-a"]
        zone.current_occupancy = int(zone.capacity * 0.75)
        assert zone.status == ZoneStatus.BUSY

    def test_critical_status(self):
        """Zone above 85% should be CRITICAL."""
        zones = create_stadium_zones()
        zone = zones["block-a"]
        zone.current_occupancy = int(zone.capacity * 0.9)
        assert zone.status == ZoneStatus.CRITICAL

    def test_closed_status(self):
        """Inactive zone should be CLOSED."""
        zones = create_stadium_zones()
        zone = zones["block-a"]
        zone.is_active = False
        assert zone.status == ZoneStatus.CLOSED

    def test_occupancy_ratio_capped_at_one(self):
        """Occupancy ratio should never exceed 1.0."""
        zones = create_stadium_zones()
        zone = zones["block-a"]
        zone.current_occupancy = zone.capacity + 100
        assert zone.occupancy_ratio == 1.0

    def test_zero_capacity_zone(self):
        """Zone with zero capacity should have 0.0 occupancy ratio."""
        zones = create_stadium_zones()
        zone = zones["block-a"]
        zone.capacity = 0
        assert zone.occupancy_ratio == 0.0
