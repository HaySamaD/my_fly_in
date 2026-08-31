"""Domain models for the Fly-in simulation system.

Defines all core entities including zones, connections, drones,
and map configurations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math


class ZoneType(str, Enum):
    """Enumeration of valid zone types and turn transit characteristics."""

    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"

    @property
    def turn_cost(self) -> int:
        """Return the movement cost in turns to enter this zone type."""
        if self is ZoneType.RESTRICTED:
            return 2
        if self in (ZoneType.NORMAL, ZoneType.PRIORITY):
            return 1
        raise ValueError(
            f"Blocked zones cannot be entered (type: {self.value})"
        )

    @property
    def is_traversable(self) -> bool:
        """Return True if drones are permitted to enter this zone type."""
        return self is not ZoneType.BLOCKED


@dataclass(slots=True)
class Zone:
    """Represents a discrete topological zone (node) in the graph."""

    name: str
    x: int
    y: int
    zone_type: ZoneType = ZoneType.NORMAL
    color: str | None = None
    max_drones: int = 1
    is_start: bool = False
    is_end: bool = False

    @property
    def effective_capacity(self) -> float | int:
        """Return maximum occupancy.

        Start and End hubs have infinite capacity by definition.
        """
        if self.is_start or self.is_end:
            return math.inf
        return self.max_drones


@dataclass(slots=True, frozen=True)
class Connection:
    """Represents a bidirectional edge between two zones."""

    zone_a: str
    zone_b: str
    max_link_capacity: int = 1

    @property
    def canonical_pair(self) -> tuple[str, str]:
        """Return a sorted tuple of connected zone names."""
        sorted_pair = sorted((self.zone_a, self.zone_b))
        return (sorted_pair[0], sorted_pair[1])

    def connects(self, zone_name: str) -> bool:
        """Check if this connection is attached to a given zone."""
        return zone_name in (self.zone_a, self.zone_b)

    def get_opposite(self, zone_name: str) -> str:
        """Return the opposite zone name given one endpoint."""
        if zone_name == self.zone_a:
            return self.zone_b
        if zone_name == self.zone_b:
            return self.zone_a
        raise ValueError(
            f"Zone '{zone_name}' is not an endpoint of this connection."
        )

    def format_name(self) -> str:
        """Return formatted connection name (e.g. 'zoneA-zoneB')."""
        return f"{self.zone_a}-{self.zone_b}"


@dataclass(slots=True)
class Drone:
    """Represents a drone navigating the zone network."""

    drone_id: int
    current_zone: str
    transit_target_zone: str | None = None
    transit_connection: Connection | None = None
    remaining_transit_turns: int = 0
    is_delivered: bool = False

    @property
    def name(self) -> str:
        """Return formatted drone identifier (e.g. 'D1', 'D2')."""
        return f"D{self.drone_id}"

    @property
    def is_in_transit(self) -> bool:
        """Return True if drone is currently traversing a 2-turn link."""
        return self.remaining_transit_turns > 0


@dataclass(slots=True)
class MapData:
    """Encapsulates the parsed configuration and topological components."""

    nb_drones: int
    start_zone_name: str
    end_zone_name: str
    zones: dict[str, Zone] = field(default_factory=dict)
    connections: list[Connection] = field(default_factory=list)
