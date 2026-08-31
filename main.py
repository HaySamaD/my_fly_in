"""Entry point for the Fly-in drone simulation system."""

from __future__ import annotations

import argparse
import sys

from src.graph import Graph
from src.gui_visualizer import PygameVisualizer
from src.parser import MapParser, ParsingError
from src.router import SpaceTimeRouter
from src.simulator import SimulationError, Simulator
from src.visualizer import Visualizer


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Fly-in: Discrete-event multi-drone routing simulator."
    )
    parser.add_argument(
        "map_file",
        type=str,
        help="Path to the map definition file.",
    )
    parser.add_argument(
        "--gui",
        "-g",
        action="store_true",
        help="Launch interactive Pygame 2D graphical visualizer.",
    )
    parser.add_argument(
        "--visualize",
        "-v",
        action="store_true",
        help="Enable live ANSI colored terminal visualization.",
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=0.25,
        help="Delay in seconds between terminal turns (default: 0.25).",
    )
    parser.add_argument(
        "--stats",
        "-s",
        action="store_true",
        help="Display performance summary statistics after simulation.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the main simulation workflow."""
    args = parse_arguments()
    try:
        # Step 1: Parse and validate map file
        parser = MapParser()
        map_data = parser.parse_file(args.map_file)

        # Step 2: Build topological graph
        graph = Graph(map_data)

        # Step 3: Compute conflict-free flight schedule
        router = SpaceTimeRouter(graph)
        plans = router.schedule_fleet(map_data.nb_drones)

        # Step 4: Execute requested mode
        if args.gui:
            gui = PygameVisualizer(graph, plans)
            gui.run()
        elif args.visualize:
            simulator = Simulator(graph, plans)
            visualizer = Visualizer(graph)
            visualizer.run_animated(simulator, delay=args.delay)
        else:
            simulator = Simulator(graph, plans)
            output_lines = simulator.run_all()
            for line in output_lines:
                print(line)

        # Step 5: Optional summary statistics
        if args.stats:
            simulator = Simulator(graph, plans)
            simulator.run_all()
            stats = simulator.get_summary_statistics()
            print("\n--- Simulation Summary ---", file=sys.stderr)
            print(f"Total Turns: {stats['total_turns']}", file=sys.stderr)
            print(f"Total Drones: {stats['total_drones']}", file=sys.stderr)
            print(
                f"Avg Turns/Drone: {stats['average_turns_per_drone']:.2f}",
                file=sys.stderr,
            )
        return 0
    except (ParsingError, SimulationError, RuntimeError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    except FileNotFoundError as err:
        print(f"File Error: {err}", file=sys.stderr)
        return 1
    except Exception as err:
        print(f"Unexpected Error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
