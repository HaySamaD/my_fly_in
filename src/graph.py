"""Custom Graph structure for Fly-in.

Implements an adjacency-list graph representation without external libraries.
"""

from __future__ import annotations

from typing import Iterator

from src.models import Connection, MapData, Zone, ZoneType


class Graph:
    """Represents the simulation graph with adjacency lookups."""

    def __init__(self, map_data: MapData) -> None:
        """Construct the graph from parsed map data.

        Args:
            map_data: Validated MapData instance.
        """
        self._zones: dict[str, Zone] = map_data.zones
        self._start_zone_name: str = map_data.start_zone_name
        self._end_zone_name: str = map_data.end_zone_name
        self._connections: list[Connection] = map_data.connections

        # Adjacency map: zone_name -> dict[neighbor_zone_name, Connection]
        self._adjacency: dict[str, dict[str, Connection]] = {
            name: {} for name in self._zones
        }
        self._build_adjacency()

    def _build_adjacency(self) -> None:
        """Populate the adjacency lookup table from connections."""
        for conn in self._connections:
            self._adjacency[conn.zone_a][conn.zone_b] = conn
            self._adjacency[conn.zone_b][conn.zone_a] = conn

    @property
    def start_zone(self) -> Zone:
        """Return the start hub Zone instance."""
        return self._zones[self._start_zone_name]

    @property
    def end_zone(self) -> Zone:
        """Return the end hub Zone instance."""
        return self._zones[self._end_zone_name]

    @property
    def zones(self) -> dict[str, Zone]:
        """Return a copy mapping of zone names to Zone instances."""
        return self._zones.copy()

    @property
    def connections(self) -> list[Connection]:
        """Return a shallow copy list of all connections."""
        return list(self._connections)

    def get_zone(self, name: str) -> Zone:
        """Retrieve a zone by its name.

        Args:
            name: Name of the zone.

        Returns:
            The matching Zone instance.

        Raises:
            KeyError: If zone name is not in the graph.
        """
        return self._zones[name]

    def get_connection(self, zone_a: str, zone_b: str) -> Connection | None:
        """Get the connection between two adjacent zones if it exists."""
        return self._adjacency.get(zone_a, {}).get(zone_b)

    def get_neighbors(self, zone_name: str) -> list[tuple[Zone, Connection]]:
        """Return (neighbor_zone, connection) pairs for traversable nodes.

        Blocked zones are strictly filtered out.

        Args:
            zone_name: Source zone name.

        Returns:
            List of valid traversable neighboring zones and their connections.
        """
        neighbors: list[tuple[Zone, Connection]] = []
        for neighbor_name, conn in self._adjacency.get(zone_name, {}).items():
            neighbor_zone = self._zones[neighbor_name]
            if neighbor_zone.zone_type != ZoneType.BLOCKED:
                neighbors.append((neighbor_zone, conn))
        return neighbors

    def __iter__(self) -> Iterator[Zone]:
        """Iterate over all zones in the graph."""
        return iter(self._zones.values())

    def __len__(self) -> int:
        """Return total number of zones."""
        return len(self._zones)
