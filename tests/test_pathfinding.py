"""Unit tests for Dijkstra pathfinding algorithm."""
from src.algorithms.dijkstra import DijkstraRouter
from src.core.enums import ZoneType
from src.core.models import Map, Zone


def test_shortest_path_costs() -> None:
    """Test zone cost evaluation and priority weighting rules."""
    map_obj = Map()
    start = Zone("start", 0, 0, zone_type=ZoneType.NORMAL)
    restricted = Zone("rest", 2, 2, zone_type=ZoneType.RESTRICTED)
    priority = Zone("prio", 5, 5, zone_type=ZoneType.PRIORITY)

    map_obj.zones = [start, restricted, priority]
    router = DijkstraRouter(map_obj)

    assert router.get_zone_cost(start) == 1
    assert router.get_zone_cost(restricted) == 2
    assert router.get_priority_score(priority) == 0
    assert router.get_priority_score(start) == 1
