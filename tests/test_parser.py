"""Unit tests for map syntax and semantic parsing."""

from __future__ import annotations

import pytest

from src.parser import MapParser, ParsingError


def test_valid_map_parsing() -> None:
    """Verify that a well-formed map parses correctly."""
    raw_map = """
    # Example map
    nb_drones: 3
    start_hub: start 0 0
    end_hub: goal 5 5
    hub: mid 2 2 [zone=priority max_drones=2]
    connection: start-mid
    connection: mid-goal
    """
    parser = MapParser()
    data = parser.parse_lines(raw_map.strip().splitlines())

    assert data.nb_drones == 3
    assert data.start_zone_name == "start"
    assert data.end_zone_name == "goal"
    assert len(data.zones) == 3
    assert len(data.connections) == 2
    assert data.zones["mid"].max_drones == 2


def test_missing_nb_drones() -> None:
    """Verify error when nb_drones is omitted."""
    raw_map = """
    start_hub: start 0 0
    end_hub: goal 5 5
    """
    parser = MapParser()
    with pytest.raises(ParsingError, match="nb_drones"):
        parser.parse_lines(raw_map.strip().splitlines())


def test_invalid_zone_name_with_dashes() -> None:
    """Verify rejection of zone names containing dashes."""
    raw_map = """
    nb_drones: 2
    start_hub: start-zone 0 0
    end_hub: goal 5 5
    """
    parser = MapParser()
    with pytest.raises(ParsingError, match="dashes"):
        parser.parse_lines(raw_map.strip().splitlines())


def test_duplicate_connections() -> None:
    """Verify bidirectional duplicate connection detection."""
    raw_map = """
    nb_drones: 2
    start_hub: start 0 0
    end_hub: goal 5 5
    connection: start-goal
    connection: goal-start
    """
    parser = MapParser()
    with pytest.raises(ParsingError, match="Duplicate connection"):
        parser.parse_lines(raw_map.strip().splitlines())


def test_invalid_zone_type() -> None:
    """Verify rejection of unknown zone types."""
    raw_map = """
    nb_drones: 2
    start_hub: start 0 0
    end_hub: goal 5 5
    hub: bonus 1 1 [zone=superfast]
    """
    parser = MapParser()
    with pytest.raises(ParsingError, match="Invalid zone type"):
        parser.parse_lines(raw_map.strip().splitlines())
