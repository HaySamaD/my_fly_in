"""Strict parser and semantic validator for Fly-in map files."""

from __future__ import annotations

from pathlib import Path
import re

from src.models import Connection, MapData, Zone, ZoneType


class ParsingError(Exception):
    """Exception raised for syntax or semantic errors in map files."""

    def __init__(self, line_num: int, message: str) -> None:
        """Initialize parsing error with line number context."""
        super().__init__(f"Line {line_num}: {message}")
        self.line_num = line_num
        self.message = message


class MapParser:
    """Parser that validates and converts map files into structured MapData."""

    _METADATA_REGEX = re.compile(r"\[(.*?)\]")
    _KEY_VAL_REGEX = re.compile(r"^([a-zA-Z_]+)=([a-zA-Z0-9_]+)$")

    def parse_file(self, file_path: str | Path) -> MapData:
        """Read and parse a map definition file.

        Args:
            file_path: Path to the target map file.

        Returns:
            Validated MapData instance.

        Raises:
            ParsingError: If any syntax or semantic rule is violated.
            FileNotFoundError: If the file does not exist.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Map file not found: {file_path}")
        with path.open("r", encoding="utf-8") as file:
            lines = file.readlines()
        return self.parse_lines(lines)

    def parse_lines(self, lines: list[str]) -> MapData:
        """Parse raw text lines from a map definition.

        Args:
            lines: List of line strings.

        Returns:
            Validated MapData instance.
        """
        nb_drones: int | None = None
        start_zone: Zone | None = None
        end_zone: Zone | None = None
        zones: dict[str, Zone] = {}
        connections: list[Connection] = []
        seen_connections: set[tuple[str, str]] = set()
        first_non_empty_evaluated = False

        for line_num, raw_line in enumerate(lines, start=1):
            # Strip comments and external whitespace
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue

            # First instruction must specify drone count
            if not first_non_empty_evaluated:
                nb_drones = self._parse_nb_drones(line, line_num)
                first_non_empty_evaluated = True
                continue

            if line.startswith(("start_hub:", "end_hub:", "hub:")):
                zone = self._parse_zone(line, line_num)
                if zone.name in zones:
                    raise ParsingError(
                        line_num, f"Duplicate zone name '{zone.name}'"
                    )
                if zone.is_start:
                    if start_zone is not None:
                        raise ParsingError(
                            line_num, "Multiple start_hub zones defined"
                        )
                    start_zone = zone
                elif zone.is_end:
                    if end_zone is not None:
                        raise ParsingError(
                            line_num, "Multiple end_hub zones defined"
                        )
                    end_zone = zone
                zones[zone.name] = zone
            elif line.startswith("connection:"):
                connection = self._parse_connection(line, line_num, zones)
                canonical_pair = connection.canonical_pair
                if canonical_pair in seen_connections:
                    raise ParsingError(
                        line_num,
                        f"Duplicate connection between '{connection.zone_a}' "
                        f"and '{connection.zone_b}'",
                    )
                seen_connections.add(canonical_pair)
                connections.append(connection)
            else:
                raise ParsingError(
                    line_num, f"Unrecognized directive: '{line}'"
                )

        if nb_drones is None:
            raise ParsingError(1, "Map file is empty or missing 'nb_drones'")
        if start_zone is None:
            raise ParsingError(
                len(lines), "Missing required 'start_hub' definition"
            )
        if end_zone is None:
            raise ParsingError(
                len(lines), "Missing required 'end_hub' definition"
            )

        return MapData(
            nb_drones=nb_drones,
            start_zone_name=start_zone.name,
            end_zone_name=end_zone.name,
            zones=zones,
            connections=connections,
        )

    def _parse_nb_drones(self, line: str, line_num: int) -> int:
        """Parse and validate the 'nb_drones: <positive_int>' line."""
        if not line.startswith("nb_drones:"):
            raise ParsingError(
                line_num,
                "Expected 'nb_drones: <count>' as first non-empty directive",
            )
        parts = line.split(":", 1)
        raw_val = parts[1].strip()
        try:
            val = int(raw_val)
            if val <= 0:
                raise ValueError
            return val
        except ValueError:
            raise ParsingError(
                line_num,
                f"'nb_drones' must be a positive integer, got '{raw_val}'",
            )

    def _parse_zone(self, line: str, line_num: int) -> Zone:
        """Parse zone declaration line and metadata block."""
        prefix, remainder = line.split(":", 1)
        is_start = prefix == "start_hub"
        is_end = prefix == "end_hub"
        remainder = remainder.strip()

        metadata_match = self._METADATA_REGEX.search(remainder)
        metadata_str = ""
        if metadata_match:
            metadata_str = metadata_match.group(1).strip()
            remainder = remainder[: metadata_match.start()].strip()

        tokens = remainder.split()
        if len(tokens) != 3:
            raise ParsingError(
                line_num,
                f"Zone declaration format must be '<name> <x> <y>', "
                f"got '{remainder}'",
            )

        name, raw_x, raw_y = tokens
        if "-" in name or " " in name:
            raise ParsingError(
                line_num,
                f"Zone name '{name}' must not contain dashes or spaces",
            )

        try:
            x = int(raw_x)
            y = int(raw_y)
        except ValueError:
            raise ParsingError(
                line_num,
                f"Coordinates must be integers, got x='{raw_x}', y='{raw_y}'",
            )

        zone_type = ZoneType.NORMAL
        color: str | None = None
        max_drones = 1

        if metadata_str:
            meta_dict = self._extract_metadata(metadata_str, line_num)
            if "zone" in meta_dict:
                raw_type = meta_dict["zone"]
                try:
                    zone_type = ZoneType(raw_type)
                except ValueError:
                    valid_types = [t.value for t in ZoneType]
                    raise ParsingError(
                        line_num,
                        f"Invalid zone type '{raw_type}'. "
                        f"Valid types: {valid_types}",
                    )
            if "color" in meta_dict:
                color = meta_dict["color"]
            if "max_drones" in meta_dict and not (is_start or is_end):
                raw_max = meta_dict["max_drones"]
                try:
                    max_drones = int(raw_max)
                    if max_drones <= 0:
                        raise ValueError
                except ValueError:
                    raise ParsingError(
                        line_num,
                        f"'max_drones' must be positive integer, "
                        f"got '{raw_max}'",
                    )

        return Zone(
            name=name,
            x=x,
            y=y,
            zone_type=zone_type,
            color=color,
            max_drones=max_drones,
            is_start=is_start,
            is_end=is_end,
        )

    def _parse_connection(
        self, line: str, line_num: int, existing_zones: dict[str, Zone]
    ) -> Connection:
        """Parse connection declaration and validate referenced zones."""
        _, remainder = line.split(":", 1)
        remainder = remainder.strip()

        metadata_match = self._METADATA_REGEX.search(remainder)
        metadata_str = ""
        if metadata_match:
            metadata_str = metadata_match.group(1).strip()
            remainder = remainder[: metadata_match.start()].strip()

        link_tokens = remainder.split("-")
        if len(link_tokens) != 2:
            raise ParsingError(
                line_num,
                f"Connection format must be '<zone1>-<zone2>', "
                f"got '{remainder}'",
            )

        zone_a = link_tokens[0].strip()
        zone_b = link_tokens[1].strip()
        if not zone_a or not zone_b or zone_a == zone_b:
            raise ParsingError(
                line_num,
                f"Invalid connection endpoints: '{zone_a}' and '{zone_b}'",
            )
        if zone_a not in existing_zones:
            raise ParsingError(
                line_num, f"Connection references undefined zone '{zone_a}'"
            )
        if zone_b not in existing_zones:
            raise ParsingError(
                line_num, f"Connection references undefined zone '{zone_b}'"
            )

        max_link_capacity = 1
        if metadata_str:
            meta_dict = self._extract_metadata(metadata_str, line_num)
            if "max_link_capacity" in meta_dict:
                raw_cap = meta_dict["max_link_capacity"]
                try:
                    max_link_capacity = int(raw_cap)
                    if max_link_capacity <= 0:
                        raise ValueError
                except ValueError:
                    raise ParsingError(
                        line_num,
                        f"'max_link_capacity' must be positive integer, "
                        f"got '{raw_cap}'",
                    )

        return Connection(
            zone_a=zone_a,
            zone_b=zone_b,
            max_link_capacity=max_link_capacity,
        )

    def _extract_metadata(
        self, metadata_str: str, line_num: int
    ) -> dict[str, str]:
        """Extract key-value pairs from metadata bracket content."""
        tags = metadata_str.split()
        result: dict[str, str] = {}
        for tag in tags:
            match = self._KEY_VAL_REGEX.match(tag)
            if not match:
                raise ParsingError(
                    line_num, f"Malformed metadata tag: '{tag}'"
                )
            key, val = match.groups()
            result[key] = val
        return result
