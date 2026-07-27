"""Unit tests for Simulation Engine execution."""
from src.core.models import Drone, Map, Zone
from src.simulation.engine import SimulationEngine


def test_engine_initialization() -> None:
    """Test simulation engine initial state."""
    map_obj = Map()
    start = Zone("start", 0, 0)
    drone = Drone("D1", current_zone=start)
    map_obj.zones.append(start)
    map_obj.drones.append(drone)

    engine = SimulationEngine(map_obj)
    assert engine.current_turn == 0
    assert not engine.is_finished()
