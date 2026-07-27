"""
Main application execution entry point for Fly-in.

Orchestrates map parsing, Dijkstra pathfinding, simulation, and visualizers.
"""
import sys

from src.algorithms.dijkstra import DijkstraRouter
from src.cli import parse_cli_args
from src.core.exceptions import FlyInError
from src.parser.map_parser import MapParser
from src.simulation.engine import SimulationEngine
from src.visualizers.pygame_gui import PygameVisualizer
from src.visualizers.terminal_rich import TerminalVisualizer


def run_simulation() -> bool:
    """Execute a single simulation instance and return reset status."""
    args = parse_cli_args()

    # 1. Parse Map
    parser = MapParser(args.map_file)
    map_obj = parser.parse()

    start_zone = parser.start_zone
    goal_zone = parser.goal_zone

    if not start_zone or not goal_zone:
        print("Error: Start or Goal hub missing.")
        sys.exit(1)

    # 2. Pathfinding via Dijkstra
    router = DijkstraRouter(map_obj)
    zone_path = router.find_shortest_path(start_zone, goal_zone)
    indexed_actions = router.build_indexed_actions(zone_path)

    # Assign calculated path to all drones
    drone_paths = {
        drone.id: indexed_actions.copy() for drone in map_obj.drones
    }

    # 3. Engine Initialization
    engine = SimulationEngine(map_obj)

    # 4. Mode Execution
    if args.viz_mode == "gui":
        gui = PygameVisualizer(
            map_obj=map_obj,
            engine=engine,
            start_zone=start_zone,
            goal_zone=goal_zone,
        )
        reset_requested = gui.run(drone_paths)
        return reset_requested

    if args.viz_mode == "terminal":
        term_vis = TerminalVisualizer(map_obj, engine)
        term_vis.print_header()

        total_moves = 0
        all_movements = engine.run_all(drone_paths)

        for turn_idx, moves_str in enumerate(all_movements, start=1):
            moves_list = moves_str.split() if moves_str else []
            total_moves += len(moves_list)
            term_vis.print_step(turn_idx, moves_list)

        term_vis.print_summary(
            total_turns=engine.current_turn, total_moves=total_moves
        )
        return False

    # Default standard stdout output format
    all_movements = engine.run_all(drone_paths)
    for moves_str in all_movements:
        if moves_str:
            print(moves_str)

    return False


def main() -> None:
    """Main program entry point with GUI reset loop."""
    should_reset = True
    while should_reset:
        should_reset = run_simulation()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Fly-in] Simulation interrupted by user.")
        sys.exit(0)
    except FlyInError as err:
        print(f"Error: {err}")
        sys.exit(1)
    except Exception as err:
        print(f"Unexpected Error: {err}")
        sys.exit(1)
