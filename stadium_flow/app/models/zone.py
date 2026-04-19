"""
Zone data models.

Represents stadium sectors/blocks with real-time occupancy tracking
and status classifications based on crowd density levels.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ZoneStatus(str, Enum):
    """Traffic status classification for a zone."""
    CLEAR = "clear"           # < 50% capacity
    MODERATE = "moderate"     # 50-70% capacity
    BUSY = "busy"             # 70-85% capacity
    CRITICAL = "critical"     # > 85% capacity
    CLOSED = "closed"         # Zone is closed/blocked


class ZoneType(str, Enum):
    """Classification of zone purpose."""
    SEATING = "seating"
    CONCOURSE = "concourse"
    ENTRY_GATE = "entry_gate"
    VIP = "vip"
    HOSPITALITY = "hospitality"
    FIELD_LEVEL = "field_level"


@dataclass
class Zone:
    """
    A discrete zone within the venue with real-time occupancy data.

    Tracks current attendee count, capacity, and computes
    congestion status dynamically.
    """
    id: str
    name: str
    zone_type: ZoneType
    capacity: int
    current_occupancy: int = 0
    adjacent_zones: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    is_accessible: bool = True
    is_active: bool = True

    # SVG map rendering coordinates
    map_x: float = 0.0
    map_y: float = 0.0
    map_path: Optional[str] = None

    @property
    def occupancy_ratio(self) -> float:
        """Current occupancy as a fraction of capacity (0.0 - 1.0)."""
        if self.capacity == 0:
            return 0.0
        return min(self.current_occupancy / self.capacity, 1.0)

    @property
    def status(self) -> ZoneStatus:
        """Compute congestion status based on occupancy ratio."""
        if not self.is_active:
            return ZoneStatus.CLOSED
        ratio = self.occupancy_ratio
        if ratio < 0.5:
            return ZoneStatus.CLEAR
        elif ratio < 0.7:
            return ZoneStatus.MODERATE
        elif ratio < 0.85:
            return ZoneStatus.BUSY
        return ZoneStatus.CRITICAL

    @property
    def available_capacity(self) -> int:
        """Remaining spots available in this zone."""
        return max(0, self.capacity - self.current_occupancy)

    def to_dict(self) -> dict:
        """Serialize zone to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "zone_type": self.zone_type.value,
            "capacity": self.capacity,
            "current_occupancy": self.current_occupancy,
            "occupancy_ratio": round(self.occupancy_ratio, 3),
            "status": self.status.value,
            "available_capacity": self.available_capacity,
            "is_accessible": self.is_accessible,
            "adjacent_zones": self.adjacent_zones,
            "map_x": self.map_x,
            "map_y": self.map_y,
        }
