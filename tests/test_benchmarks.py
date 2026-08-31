"""Comprehensive benchmark test suite across all project difficulty tiers."""

from __future__ import annotations

from pathlib import Path

from src.graph import Graph
from src.parser import MapParser
from src.router import SpaceTimeRouter
from src.simulator import Simulator


def _run_map_file(relative_path: str) -> int:
    """Parse, route, simulate and return total turns for a map file."""
    path = Path(relative_path)
    parser = MapParser()
    map_data = parser.parse_file(path)
    graph = Graph(map_data)
    router = SpaceTimeRouter(graph)
    plans = router.schedule_fleet(map_data.nb_drones)
    simulator = Simulator(graph, plans)
    simulator.run_all()
    return simulator.current_turn


# ============================================================================
# Easy Tier Benchmarks (Target: < 10 turns)
# ============================================================================


def test_easy_01_linear_path() -> None:
    """Easy 1 - Linear path (2 drones): Target <= 6 turns."""
    turns = _run_map_file("maps/easy/01_linear_path.txt")
    assert turns <= 6


def test_easy_02_simple_fork() -> None:
    """Easy 2 - Simple fork (4 drones): Target <= 8 turns."""
    turns = _run_map_file("maps/easy/02_simple_fork.txt")
    assert turns <= 8


def test_easy_03_basic_capacity() -> None:
    """Easy 3 - Basic capacity (4 drones): Target <= 6 turns."""
    turns = _run_map_file("maps/easy/03_basic_capacity.txt")
    assert turns <= 6


# ============================================================================
# Medium Tier Benchmarks (Target: 10 - 30 turns)
# ============================================================================


def test_medium_01_dead_end_trap() -> None:
    """Medium 1 - Dead end trap (5 drones): Target <= 12 turns."""
    turns = _run_map_file("maps/medium/01_dead_end_trap.txt")
    assert turns <= 12


def test_medium_02_circular_loop() -> None:
    """Medium 2 - Circular loop (6 drones): Target <= 15 turns."""
    turns = _run_map_file("maps/medium/02_circular_loop.txt")
    assert turns <= 15


def test_medium_03_priority_puzzle() -> None:
    """Medium 3 - Priority puzzle (5 drones): Target <= 12 turns."""
    turns = _run_map_file("maps/medium/03_priority_puzzle.txt")
    assert turns <= 12


# ============================================================================
# Hard Tier Benchmarks (Target: < 45-60 turns)
# ============================================================================


def test_hard_01_maze_nightmare() -> None:
    """Hard 1 - Maze nightmare (8 drones): Target <= 30 turns."""
    turns = _run_map_file("maps/hard/01_maze_nightmare.txt")
    assert turns <= 30


def test_hard_02_capacity_hell() -> None:
    """Hard 2 - Capacity hell (12 drones): Target <= 35 turns."""
    turns = _run_map_file("maps/hard/02_capacity_hell.txt")
    assert turns <= 35


def test_hard_03_ultimate_challenge() -> None:
    """Hard 3 - Ultimate challenge (15 drones): Target <= 45 turns."""
    turns = _run_map_file("maps/hard/03_ultimate_challenge.txt")
    assert turns <= 45


# ============================================================================
# Challenger Map (Bonus Tier: The Impossible Dream)
# ============================================================================


def test_challenger_01_the_impossible_dream() -> None:
    """Challenger - The Impossible Dream (25 drones): Beat 45 turns."""
    turns = _run_map_file("maps/challenger/01_the_impossible_dream.txt")
    assert turns <= 45
