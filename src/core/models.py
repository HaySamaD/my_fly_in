"""
Core domain models representing Zones, Connections, Drones, and the Map graph.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from src.core.enums import DroneStatus, ZoneType
from src.core.exceptions import MapValidationError


@dataclass
class Zone:
    """Represents a graph node (hub/zone) in the simulation network."""

    name: str
    x: int
    y: int
    color: Optional[str] = None
    max_drones: int = 1
    zone_type: ZoneType = ZoneType.NORMAL
    drones_present: List[Drone] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate capacity constraints post initialization."""
        if self.max_drones <= 0:
            raise MapValidationError(
                f"Zone '{self.name}' max_drones must be positive."
            )

    def add_drone(self, drone: Drone) -> None:
        """Add drone to zone while checking capacity bounds."""
        if len(self.drones_present) >= self.max_drones:
            raise MapValidationError(f"Zone '{self.name}' capacity breached.")
        self.drones_present.append(drone)
        drone.current_zone = self

    def remove_drone(self, drone: Drone) -> None:
        """Remove drone from zone."""
        if drone in self.drones_present:
            self.drones_present.remove(drone)
            drone.current_zone = None


@dataclass
class Drone:
    """Represents an autonomous navigating drone agent."""

    id: str
    current_zone: Optional[Zone] = None
    status: DroneStatus = DroneStatus.IDLE
    current_step: int = 0


@dataclass
class Connection:
    """Represents an edge link connecting two zones."""

    from_zone: Zone
    to_zone: Zone
    max_links: int = 1
    drones_on_link: List[Drone] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate connection capacity rules."""
        if self.max_links <= 0:
            raise MapValidationError(
                f"Link '{self.from_zone.name}-{self.to_zone.name}' "
                "max_links must be positive."
            )

    def add_drone(self, drone: Drone) -> None:
        """Add drone to connection link."""
        if len(self.drones_on_link) >= self.max_links:
            raise MapValidationError("Connection link capacity breached.")
        self.drones_on_link.append(drone)

    def remove_drone(self, drone: Drone) -> None:
        """Remove drone from connection link."""
        if drone in self.drones_on_link:
            self.drones_on_link.remove(drone)


@dataclass
class Map:
    """Represents the complete simulation network graph."""

    zones: List[Zone] = field(default_factory=list)
    connections: List[Connection] = field(default_factory=list)
    drones: List[Drone] = field(default_factory=list)

    def find_zone(self, name: str) -> Optional[Zone]:
        """Find zone model by name."""
        for zone in self.zones:
            if zone.name == name:
                return zone
        return None

    def find_connection(self, z1: Zone, z2: Zone) -> Optional[Connection]:
        """Find bidirectional connection between two zones."""
        for conn in self.connections:
            if (conn.from_zone == z1 and conn.to_zone == z2) or (
                conn.from_zone == z2 and conn.to_zone == z1
            ):
                return conn
        return None

    def neighbors(self, zone: Zone) -> List[Zone]:
        """Return accessible (non-blocked) neighboring zones."""
        result: List[Zone] = []
        for conn in self.connections:
            if (
                conn.from_zone == zone
                and conn.to_zone.zone_type != ZoneType.BLOCKED
            ):
                result.append(conn.to_zone)
            elif (
                conn.to_zone == zone
                and conn.from_zone.zone_type != ZoneType.BLOCKED
            ):
                result.append(conn.from_zone)
        return result
