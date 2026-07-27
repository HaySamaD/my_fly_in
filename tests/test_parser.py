"""Unit tests for MapParser module."""
from pathlib import Path
import pytest
from src.core.exceptions import MapParseError, MapValidationError
from src.parser.map_parser import MapParser


def test_parse_valid_map(tmp_path: Path) -> None:
    """Test parsing a fully valid text map file."""
    map_content = (
        "nb_drones: 2\n"
        "start_hub: start 0 0\n"
        "end_hub: goal 10 10\n"
        "connection: start-goal\n"
    )
    map_file = tmp_path / "test_map.txt"
    map_file.write_text(map_content, encoding="utf-8")

    parser = MapParser(map_file)
    map_obj = parser.parse()

    assert len(map_obj.drones) == 2
    assert map_obj.find_zone("start") is not None
    assert map_obj.find_zone("goal") is not None


def test_missing_nb_drones(tmp_path: Path) -> None:
    """Test parser raises MapParseError when nb_drones header is missing."""
    map_content = "start_hub: start 0 0\nend_hub: goal 10 10\n"
    map_file = tmp_path / "bad_map.txt"
    map_file.write_text(map_content, encoding="utf-8")

    parser = MapParser(map_file)
    with pytest.raises(MapParseError):
        parser.parse()


def test_missing_hubs(tmp_path: Path) -> None:
    """Test parser raises MapValidationError when hubs are incomplete."""
    map_content = "nb_drones: 1\nstart_hub: start 0 0\n"
    map_file = tmp_path / "no_goal.txt"
    map_file.write_text(map_content, encoding="utf-8")

    parser = MapParser(map_file)
    with pytest.raises(MapValidationError):
        parser.parse()
