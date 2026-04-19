"""
Venue data models.

Defines the core Venue entity with stadium topology,
including zones, entry gates, and facility locations.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class VenueType(str, Enum):
    """Classification of sporting venue types."""
    STADIUM = "stadium"
    ARENA = "arena"
    FIELD = "field"


class FacilityType(str, Enum):
    """Types of facilities within a venue."""
    RESTROOM = "restroom"
    CONCESSION = "concession"
    MERCHANDISE = "merchandise"
    FIRST_AID = "first_aid"
    INFORMATION = "information"
    EXIT = "exit"
    ENTRY = "entry"
    ELEVATOR = "elevator"
    PARKING = "parking"


@dataclass
class GeoCoordinate:
    """Geographic coordinate for mapping integration."""
    latitude: float
    longitude: float


@dataclass
class Facility:
    """A specific facility within the venue."""
    id: str
    name: str
    facility_type: FacilityType
    zone_id: str
    position_x: float = 0.0
    position_y: float = 0.0
    is_accessible: bool = True
    current_wait_minutes: float = 0.0


@dataclass
class Venue:
    """
    Top-level venue entity representing a sporting stadium.

    Contains metadata, geographic location, and collections
    of zones and facilities.
    """
    id: str
    name: str
    venue_type: VenueType
    max_capacity: int
    location: Optional[GeoCoordinate] = None
    address: str = ""
    zones: list[str] = field(default_factory=list)
    facilities: list[Facility] = field(default_factory=list)
    is_active: bool = True
