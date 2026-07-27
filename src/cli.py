"""
Command Line Interface (CLI) argument parser for Fly-in.
"""
import argparse
from pathlib import Path


class CLIArgs:
    """Container for parsed CLI options."""

    def __init__(self, map_file: Path, viz_mode: str) -> None:
        self.map_file = map_file
        self.viz_mode = viz_mode


def parse_cli_args() -> CLIArgs:
    """Parse command line flags and map path argument."""
    parser = argparse.ArgumentParser(
        description="Fly-in: Capacity-constrained drone routing simulator."
    )

    parser.add_argument(
        "map_file",
        type=str,
        help="Path to the map text configuration file.",
    )

    parser.add_argument(
        "--viz",
        type=str,
        choices=["terminal", "gui", "none"],
        default="terminal",
        help="Visualization mode: 'terminal', 'gui' (Pygame), or 'none'.",
    )

    args = parser.parse_args()
    return CLIArgs(map_file=Path(args.map_file), viz_mode=args.viz)
