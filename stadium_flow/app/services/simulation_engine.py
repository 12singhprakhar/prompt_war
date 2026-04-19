"""
Crowd Simulation Engine.

Agent-based crowd simulation for modeling attendee movement
across stadium zones. Supports configurable arrival/departure
patterns and realistic density distribution.
"""

import asyncio
import logging
import math
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from app.models.zone import Zone, ZoneType

logger = logging.getLogger(__name__)


# ── Narendra Modi Stadium Topology ────────────────────────────────
def create_stadium_zones() -> dict[str, Zone]:
    """
    Create the zone topology for the Narendra Modi Stadium.

    Returns a dictionary of Zone objects keyed by zone ID, representing
    the 24-block alphabetical seating layout plus concourse and gates.
    """
    zones: dict[str, Zone] = {}

    # Seating blocks A-R (18 blocks, main spectator sections)
    block_configs = [
        ("A", 7500), ("B", 7200), ("C", 7000), ("D", 7300),
        ("E", 7100), ("F", 7400), ("G", 7000), ("H", 7200),
        ("I", 6800), ("J", 7500), ("K", 7100), ("L", 7000),
        ("M", 7300), ("N", 7200), ("O", 7400), ("P", 7000),
        ("Q", 6900), ("R", 7100),
    ]

    # Arrange blocks in a circle for the map
    num_blocks = len(block_configs)
    cx, cy, radius = 400, 300, 220
    for i, (letter, capacity) in enumerate(block_configs):
        angle = (2 * math.pi * i / num_blocks) - (math.pi / 2)
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)

        # Adjacent blocks are neighbors in the circle
        prev_idx = (i - 1) % num_blocks
        next_idx = (i + 1) % num_blocks
        prev_letter = block_configs[prev_idx][0]
        next_letter = block_configs[next_idx][0]

        zones[f"block-{letter.lower()}"] = Zone(
            id=f"block-{letter.lower()}",
            name=f"Block {letter}",
            zone_type=ZoneType.SEATING,
            capacity=capacity,
            adjacent_zones=[
                f"block-{prev_letter.lower()}",
                f"block-{next_letter.lower()}",
                f"concourse-{('north' if y < cy else 'south')}",
            ],
            map_x=round(x, 1),
            map_y=round(y, 1),
        )

    # VIP and hospitality zones
    zones["presidential-suite"] = Zone(
        id="presidential-suite",
        name="Presidential Suite",
        zone_type=ZoneType.VIP,
        capacity=500,
        adjacent_zones=["concourse-north", "block-a"],
        is_accessible=True,
        map_x=400, map_y=120,
    )
    zones["premium-gallery"] = Zone(
        id="premium-gallery",
        name="Premium Gallery",
        zone_type=ZoneType.HOSPITALITY,
        capacity=2000,
        adjacent_zones=["concourse-south", "block-j"],
        is_accessible=True,
        map_x=400, map_y=480,
    )

    # Concourse rings
    zones["concourse-north"] = Zone(
        id="concourse-north",
        name="North Concourse",
        zone_type=ZoneType.CONCOURSE,
        capacity=8000,
        adjacent_zones=[
            "gate-1", "gate-2", "block-a", "block-b", "block-r",
            "block-q", "presidential-suite",
        ],
        map_x=400, map_y=160,
    )
    zones["concourse-south"] = Zone(
        id="concourse-south",
        name="South Concourse",
        zone_type=ZoneType.CONCOURSE,
        capacity=8000,
        adjacent_zones=[
            "gate-3", "gate-4", "block-i", "block-j", "block-k",
            "block-l", "premium-gallery",
        ],
        map_x=400, map_y=440,
    )
    zones["concourse-east"] = Zone(
        id="concourse-east",
        name="East Concourse",
        zone_type=ZoneType.CONCOURSE,
        capacity=6000,
        adjacent_zones=[
            "gate-5", "block-e", "block-f", "block-g",
            "concourse-north", "concourse-south",
        ],
        map_x=580, map_y=300,
    )
    zones["concourse-west"] = Zone(
        id="concourse-west",
        name="West Concourse",
        zone_type=ZoneType.CONCOURSE,
        capacity=6000,
        adjacent_zones=[
            "gate-6", "block-n", "block-o", "block-p",
            "concourse-north", "concourse-south",
        ],
        map_x=220, map_y=300,
    )

    # Entry gates
    gate_configs = [
        ("gate-1", "Gate 1 — North Main", 340, 60),
        ("gate-2", "Gate 2 — North East", 500, 80),
        ("gate-3", "Gate 3 — South Main", 340, 540),
        ("gate-4", "Gate 4 — South East", 500, 520),
        ("gate-5", "Gate 5 — East", 680, 300),
        ("gate-6", "Gate 6 — West", 120, 300),
    ]
    for gate_id, name, gx, gy in gate_configs:
        zones[gate_id] = Zone(
            id=gate_id,
            name=name,
            zone_type=ZoneType.ENTRY_GATE,
            capacity=3000,
            adjacent_zones=[],  # Will be linked to nearest concourse
            map_x=gx, map_y=gy,
        )

    # Link gates to concourses
    zones["gate-1"].adjacent_zones = ["concourse-north"]
    zones["gate-2"].adjacent_zones = ["concourse-north", "concourse-east"]
    zones["gate-3"].adjacent_zones = ["concourse-south"]
    zones["gate-4"].adjacent_zones = ["concourse-south", "concourse-east"]
    zones["gate-5"].adjacent_zones = ["concourse-east"]
    zones["gate-6"].adjacent_zones = ["concourse-west"]

    return zones


class SimulationEngine:
    """
    Discrete event simulation engine for crowd dynamics.

    Simulates attendee movement across venue zones using an
    agent-based model with configurable parameters. Publishes
    zone state updates via registered callbacks.
    """

    def __init__(
        self,
        initial_count: int = 45000,
        max_capacity: int = 132000,
        tick_interval: float = 2.0,
    ) -> None:
        self.zones = create_stadium_zones()
        self.max_capacity = max_capacity
        self.tick_interval = tick_interval
        self.is_running = False
        self.tick_count = 0
        self.total_attendees = 0
        self.analytics_service = None

        # Simulation metrics
        self.peak_occupancy = 0
        self.total_served = 0
        self.start_time: Optional[datetime] = None

        # Event callbacks for broadcasting updates
        self._callbacks: list[Callable] = []

        # Initialize crowd distribution
        self._distribute_initial_crowd(initial_count)

    def _distribute_initial_crowd(self, total: int) -> None:
        """
        Distribute attendees across seating zones proportionally.

        Uses weighted random distribution based on zone capacity
        to create a realistic initial state.
        """
        seating_zones = [
            z for z in self.zones.values()
            if z.zone_type == ZoneType.SEATING
        ]
        total_capacity = sum(z.capacity for z in seating_zones)

        remaining = total
        for i, zone in enumerate(seating_zones):
            if i == len(seating_zones) - 1:
                zone.current_occupancy = min(remaining, zone.capacity)
                remaining -= zone.current_occupancy
            else:
                proportion = zone.capacity / total_capacity
                count = int(total * proportion * random.uniform(0.7, 1.1))
                count = min(count, zone.capacity, remaining)
                zone.current_occupancy = count
                remaining -= count

        # Distribute any overflow across zones with remaining capacity
        if remaining > 0:
            for zone in seating_zones:
                if remaining <= 0:
                    break
                space = zone.capacity - zone.current_occupancy
                add = min(space, remaining)
                zone.current_occupancy += add
                remaining -= add

        self.total_attendees = total
        self.peak_occupancy = total
        self.total_served = total
        logger.info(
            "Distributed %d attendees across %d zones",
            total, len(seating_zones),
        )

    def register_callback(self, callback: Callable) -> None:
        """Register a callback for zone state updates."""
        self._callbacks.append(callback)

    async def start(self) -> None:
        """Start the simulation loop."""
        self.is_running = True
        self.start_time = datetime.now(timezone.utc)
        logger.info("Simulation engine started (tick=%.1fs)", self.tick_interval)

        while self.is_running:
            await self._tick()
            await asyncio.sleep(self.tick_interval)

    async def stop(self) -> None:
        """Stop the simulation loop gracefully."""
        self.is_running = False
        logger.info("Simulation engine stopped after %d ticks", self.tick_count)

    async def _tick(self) -> None:
        """
        Execute a single simulation tick.

        Each tick simulates:
        1. Match phase updates
        2. New arrivals at entry gates
        3. Movement from gates to concourses
        4. Movement from concourses to seating
        5. Random inter-zone movement (restroom, concessions)
        6. Departures (late-game exit pattern)
        """
        self.tick_count += 1
        
        # Determine match phase based on logical ticks (e.g. 1 tick = 1 "minute" roughly)
        match_time = self.tick_count % 300
        if match_time < 45:
            self.match_phase = "Pre-Match"
            arrival_rate = max(0, 300 - match_time * 5) * random.uniform(0.5, 1.5)
            departure_rate = 0
            facility_chance = 0.05
        elif match_time < 135:
            self.match_phase = "1st Half"
            arrival_rate = random.randint(0, 10)
            departure_rate = 0
            facility_chance = 0.01  # People stay glued to seats
        elif match_time < 150:
            self.match_phase = "Halftime"
            arrival_rate = 0
            departure_rate = random.randint(0, 5)
            facility_chance = 0.25  # Massive surge to concourse
        elif match_time < 240:
            self.match_phase = "2nd Half"
            arrival_rate = 0
            departure_rate = random.randint(0, 15) if match_time > 200 else 0
            facility_chance = 0.02
        else:
            self.match_phase = "Post-Match"
            arrival_rate = 0
            departure_rate = min((match_time - 240) * 5, 200) * random.uniform(0.5, 1.5)
            facility_chance = 0.00
            
        # Phase 1: Arrivals
        arrival_rate = int(arrival_rate)
        if self.total_attendees + arrival_rate <= self.max_capacity and arrival_rate > 0:
            self._simulate_arrivals(arrival_rate)

        # Phase 2: Internal movement
        self._simulate_movement()

        # Phase 3: Concession/restroom traffic based on match phase
        self._simulate_facility_traffic(facility_chance)

        # Phase 4: Departures
        if departure_rate > 0:
            self._simulate_departures(int(departure_rate))

        # Update metrics
        self.total_attendees = sum(z.current_occupancy for z in self.zones.values())
        self.peak_occupancy = max(self.peak_occupancy, self.total_attendees)

        # Notify listeners
        state = self.get_state()
        for callback in self._callbacks:
            try:
                await callback(state)
            except Exception as e:
                logger.error("Callback error: %s", e)

    def _simulate_arrivals(self, count: int) -> None:
        """Distribute new arrivals across entry gates."""
        gates = [z for z in self.zones.values() if z.zone_type == ZoneType.ENTRY_GATE]
        for _ in range(count):
            gate = random.choice(gates)
            if gate.current_occupancy < gate.capacity:
                gate.current_occupancy += 1
                self.total_served += 1

    def _simulate_movement(self) -> None:
        """
        Simulate flow between adjacent zones.

        Movement probability is proportional to congestion differential:
        people move away from crowded zones toward less crowded ones.
        """
        movements: list[tuple[str, str, int]] = []

        for zone in self.zones.values():
            if zone.current_occupancy == 0:
                continue

            # Gate → Concourse flow (entry funneling)
            if zone.zone_type == ZoneType.ENTRY_GATE and zone.current_occupancy > 0:
                for adj_id in zone.adjacent_zones:
                    adj = self.zones.get(adj_id)
                    if adj and adj.current_occupancy < adj.capacity:
                        move_count = min(
                            int(zone.current_occupancy * 0.3),
                            adj.available_capacity,
                        )
                        if move_count > 0:
                            movements.append((zone.id, adj_id, move_count))

            # Concourse → Seating flow
            elif zone.zone_type == ZoneType.CONCOURSE:
                seating_neighbors = [
                    z_id for z_id in zone.adjacent_zones
                    if z_id.startswith("block-")
                ]
                if seating_neighbors and zone.current_occupancy > 50:
                    target_id = random.choice(seating_neighbors)
                    target = self.zones.get(target_id)
                    if target and target.occupancy_ratio < 0.95:
                        move_count = min(
                            random.randint(5, 30),
                            target.available_capacity,
                            zone.current_occupancy,
                        )
                        movements.append((zone.id, target_id, move_count))

            # Random inter-zone movement (5% chance per zone per tick)
            elif random.random() < 0.05:
                if zone.adjacent_zones:
                    target_id = random.choice(zone.adjacent_zones)
                    target = self.zones.get(target_id)
                    if target and target.available_capacity > 0:
                        move_count = min(
                            random.randint(1, 10),
                            target.available_capacity,
                            zone.current_occupancy,
                        )
                        movements.append((zone.id, target_id, move_count))

        # Apply all movements atomically
        for from_id, to_id, count in movements:
            from_zone = self.zones[from_id]
            to_zone = self.zones[to_id]
            actual = min(count, from_zone.current_occupancy, to_zone.available_capacity)
            if actual > 0:
                from_zone.current_occupancy -= actual
                to_zone.current_occupancy += actual

    def _simulate_facility_traffic(self, chance: float) -> None:
        """
        Simulate attendees visiting concessions/restrooms.

        Moves small groups from seating to concourse and back,
        representing periodic facility visits. Number scales with chance.
        """
        for zone in list(self.zones.values()):
            if zone.zone_type != ZoneType.SEATING:
                continue
            if random.random() < chance:
                concourse_neighbors = [
                    z_id for z_id in zone.adjacent_zones
                    if z_id.startswith("concourse-")
                ]
                if concourse_neighbors:
                    concourse_id = concourse_neighbors[0]
                    concourse = self.zones.get(concourse_id)
                    if concourse and concourse.available_capacity > 0:
                        count = min(
                            random.randint(1, 5),
                            zone.current_occupancy,
                            concourse.available_capacity,
                        )
                        zone.current_occupancy -= count
                        concourse.current_occupancy += count

    def _simulate_departures(self, count: int) -> None:
        """Remove attendees from entry gates (exits)."""
        gates = [z for z in self.zones.values() if z.zone_type == ZoneType.ENTRY_GATE]
        for _ in range(count):
            gate = random.choice(gates)
            if gate.current_occupancy > 0:
                gate.current_occupancy -= 1

    def get_state(self) -> dict[str, Any]:
        """
        Get complete simulation state for broadcasting.

        Returns:
            Dictionary containing all zone states and aggregate metrics.
        """
        zones_data = {
            zone_id: zone.to_dict() for zone_id, zone in self.zones.items()
        }

        total = sum(z.current_occupancy for z in self.zones.values())
        critical_zones = [
            z.id for z in self.zones.values()
            if z.status.value == "critical"
        ]
        
        avg_wait = 0.0
        if self.analytics_service:
            concourse_zones = [z for z in self.zones.values() if z.zone_type.value == "concourse"]
            if concourse_zones:
                avg_wait = sum(
                    self.analytics_service.estimate_wait_time(z.id) for z in concourse_zones
                ) / len(concourse_zones)

        return {
            "tick": self.tick_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "match_phase": getattr(self, "match_phase", "Pre-Match"),
            "zones": zones_data,
            "metrics": {
                "total_attendees": total,
                "max_capacity": self.max_capacity,
                "occupancy_percentage": round(total / self.max_capacity * 100, 1),
                "peak_occupancy": self.peak_occupancy,
                "total_served": self.total_served,
                "critical_zones": len(critical_zones),
                "critical_zone_ids": critical_zones,
                "avg_wait_time_minutes": round(avg_wait, 1),
            },
        }

    def get_zone(self, zone_id: str) -> Optional[Zone]:
        """Get a specific zone by ID."""
        return self.zones.get(zone_id)

    def get_all_zones(self) -> list[Zone]:
        """Get all zones."""
        return list(self.zones.values())
