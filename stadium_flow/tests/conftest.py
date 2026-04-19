"""
Shared test fixtures and configuration.
"""

import pytest
from unittest.mock import AsyncMock

from app.services.simulation_engine import SimulationEngine, create_stadium_zones
from app.services.routing_engine import RoutingEngine
from app.services.crowd_analytics import CrowdAnalytics
from app.agents.base_agent import SharedMemory


@pytest.fixture
def stadium_zones():
    """Provide a fresh set of stadium zones."""
    return create_stadium_zones()


@pytest.fixture
def simulation_engine():
    """Provide a simulation engine with default configuration."""
    return SimulationEngine(
        initial_count=10000,
        max_capacity=132000,
        tick_interval=1.0,
    )


@pytest.fixture
def routing_engine(stadium_zones):
    """Provide a routing engine with the full stadium topology."""
    return RoutingEngine(stadium_zones)


@pytest.fixture
def crowd_analytics(stadium_zones):
    """Provide a crowd analytics instance."""
    return CrowdAnalytics(stadium_zones)


@pytest.fixture
def shared_memory():
    """Provide a fresh shared memory bus."""
    return SharedMemory()
