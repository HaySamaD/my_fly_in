"""
Robust map file parser for the Fly-in drone routing engine.

Parses zones, connections, and metadata while guaranteeing graph validity.
"""
import re
from pathlib import Path
from typing import List, Optional, Set, Tuple

from src.core.enums import ZoneType
from src.core.exceptions import MapParseError, MapValidationError
from src.core.models import Connection, Drone, Map, Zone


class MapParser:
    """Parser responsible for loading, validating, and building Map models."""

    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)
        self.lines: List[Tuple[int, str]] = []
        self.map_obj = Map()
        self.seen_zones: Set[str] = set()
        self.seen_connections: Set[frozenset[str]] = set()
        self.start_zone: Optional[Zone] = None
        self.goal_zone: Optional[Zone] = None

    def read_lines(self) -> List[Tuple[int, str]]:
        """Read file and strip comments and empty lines."""
        if not self.file_path.is_file():
            raise MapParseError(f"File not found: '{self.file_path}'")

        cleaned: List[Tuple[int, str]] = []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                for idx, raw in enumerate(f, start=1):
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    if " #" in line:
                        line = line.split(" #", 1)[0].strip()
                    cleaned.append((idx, line))
        except Exception as err:
            raise MapParseError(f"Failed to read map file: {err}")

        self.lines = cleaned
        return cleaned

    def _parse_nb_drones(self, line: str, line_num: int) -> int:
        """Parse number of drones header."""
        if not line.startswith("nb_drones:"):
            raise MapParseError(
                "Expected 'nb_drones: <int>' header on first line",
                line_num,
                line,
            )

        _, val_str = line.split(":", 1)
        try:
            nb = int(val_str.strip())
            if nb <= 0:
                raise ValueError()
            return nb
        except ValueError:
            raise MapParseError(
                "nb_drones must be a positive integer", line_num, line
            )

    def _parse_metadata(
        self, attr_str: str, line_num: int
    ) -> dict[str, str]:
        """Extract metadata tags inside square brackets [k1=v1 k2=v2]."""
        metadata: dict[str, str] = {}
        cleaned = attr_str.strip("[]").strip()
        if not cleaned:
            return metadata

        tokens = cleaned.split()
        for token in tokens:
            if "=" not in token:
                raise MapParseError(
                    f"Invalid metadata format '{token}'", line_num
                )
            k, v = token.split("=", 1)
            metadata[k.strip().lower()] = v.strip().lower()
        return metadata

    def _parse_zone_line(self, line: str, line_num: int) -> Zone:
        """Parse zone declaration line."""
        prefix, rest = line.split(":", 1)
        prefix = prefix.strip()
        rest = rest.strip()

        pattern = r"^([^\s-]+)\s+(-?\d+)\s+(-?\d+)\s*(\[.*\])?$"
        match = re.match(pattern, rest)
        if not match:
            raise MapParseError(
                "Invalid zone format. Zone names must not contain dashes",
                line_num,
                line,
            )

        name, x_str, y_str, raw_attrs = match.groups()

        if name in self.seen_zones:
            raise MapParseError(
                f"Duplicate zone name '{name}'", line_num, line
            )

        x, y = int(x_str), int(y_str)
        color: Optional[str] = None
        max_drones = 1
        zone_type = ZoneType.NORMAL

        if raw_attrs:
            meta = self._parse_metadata(raw_attrs, line_num)
            color = meta.get("color", color)
            if "max_drones" in meta:
                try:
                    max_drones = int(meta["max_drones"])
                    if max_drones <= 0:
                        raise ValueError()
                except ValueError:
                    raise MapParseError(
                        "max_drones must be positive", line_num, line
                    )
            if "zone" in meta:
                try:
                    zone_type = ZoneType(meta["zone"])
                except ValueError:
                    raise MapParseError(
                        f"Unknown zone type '{meta['zone']}'", line_num, line
                    )

        zone = Zone(
            name=name,
            x=x,
            y=y,
            color=color,
            max_drones=max_drones,
            zone_type=zone_type,
        )

        if prefix == "start_hub":
            if self.start_zone is not None:
                raise MapParseError(
                    "Multiple start_hub definitions", line_num, line
                )
            self.start_zone = zone
        elif prefix == "end_hub":
            if self.goal_zone is not None:
                raise MapParseError(
                    "Multiple end_hub definitions", line_num, line
                )
            self.goal_zone = zone

        self.seen_zones.add(name)
        return zone

    def _parse_connection_line(self, line: str, line_num: int) -> Connection:
        """Parse connection line declaration."""
        _, rest = line.split(":", 1)
        rest = rest.strip()

        match = re.match(r"^([^\s-]+)-([^\s-]+)\s*(\[.*\])?$", rest)
        if not match:
            raise MapParseError("Invalid connection syntax", line_num, line)

        from_name, to_name, raw_attrs = match.groups()
        from_zone = self.map_obj.find_zone(from_name)
        to_zone = self.map_obj.find_zone(to_name)

        if not from_zone or not to_zone:
            raise MapParseError(
                "Connection references unknown zone "
                f"('{from_name}', '{to_name}')",
                line_num,
                line,
            )

        conn_key = frozenset([from_name, to_name])
        if conn_key in self.seen_connections:
            raise MapParseError(
                f"Duplicate connection between '{from_name}' and '{to_name}'",
                line_num,
                line,
            )

        max_links = 1
        if raw_attrs:
            meta = self._parse_metadata(raw_attrs, line_num)
            if "max_link_capacity" in meta:
                try:
                    max_links = int(meta["max_link_capacity"])
                    if max_links <= 0:
                        raise ValueError()
                except ValueError:
                    raise MapParseError(
                        "max_link_capacity must be positive", line_num, line
                    )

        self.seen_connections.add(conn_key)
        return Connection(
            from_zone=from_zone, to_zone=to_zone, max_links=max_links
        )

    def parse(self) -> Map:
        """Execute map parsing and topology validation."""
        lines = self.read_lines()
        if not lines:
            raise MapParseError("Map file is empty")

        nb_drones = self._parse_nb_drones(lines[0][1], lines[0][0])

        # Parse Zones
        for line_num, line in lines[1:]:
            prefixes = ("hub:", "start_hub:", "end_hub:")
            if any(line.startswith(p) for p in prefixes):
                zone = self._parse_zone_line(line, line_num)
                self.map_obj.zones.append(zone)

        if not self.start_zone or not self.goal_zone:
            raise MapValidationError(
                "Map must define exactly one start_hub and one end_hub"
            )

        if (
            self.start_zone.zone_type == ZoneType.BLOCKED
            or self.goal_zone.zone_type == ZoneType.BLOCKED
        ):
            raise MapValidationError("Start or Goal hub cannot be BLOCKED")

        self.start_zone.max_drones = nb_drones
        self.goal_zone.max_drones = nb_drones

        # Parse Connections
        for line_num, line in lines[1:]:
            if line.startswith("connection:"):
                conn = self._parse_connection_line(line, line_num)
                self.map_obj.connections.append(conn)

        # Initialize Drones
        for i in range(1, nb_drones + 1):
            drone = Drone(id=f"D{i}", current_zone=self.start_zone)
            self.map_obj.drones.append(drone)
            self.start_zone.add_drone(drone)

        if not self._is_reachable(self.start_zone, self.goal_zone):
            raise MapValidationError(
                f"Goal '{self.goal_zone.name}' unreachable from start"
            )

        return self.map_obj

    def _is_reachable(self, start: Zone, goal: Zone) -> bool:
        """BFS graph reachability check."""
        visited: Set[str] = set()
        queue: List[Zone] = [start]

        while queue:
            curr = queue.pop(0)
            if curr == goal:
                return True
            visited.add(curr.name)
            for nb in self.map_obj.neighbors(curr):
                if nb.name not in visited and nb not in queue:
                    queue.append(nb)
        return False
