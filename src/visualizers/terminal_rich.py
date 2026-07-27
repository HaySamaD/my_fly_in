"""
Rich terminal visualizer for clean formatted CLI output.
"""
from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.models import Map
from src.simulation.engine import SimulationEngine


class TerminalVisualizer:
    """Rich-based terminal output renderer."""

    def __init__(self, map_obj: Map, engine: SimulationEngine) -> None:
        self.console = Console()
        self.map = map_obj
        self.engine = engine

    def print_header(self) -> None:
        """Display simulation header banner."""
        self.console.print(
            Panel.fit(
                "[bold cyan]Fly-in Drone Routing Simulation[/bold cyan]\n"
                f"Total Drones: {len(self.map.drones)}",
                title="🚁 42 School Project",
                border_style="green",
            )
        )

    def print_step(self, turn: int, movements: List[str]) -> None:
        """Print turn-by-turn movement string line."""
        moves_str = " ".join(movements) if movements else "(no movement)"
        self.console.print(
            f"[bold yellow]Turn {turn}:[/bold yellow] {moves_str}")

    def print_summary(self, total_turns: int, total_moves: int) -> None:
        """Render summary statistical table upon simulation completion."""
        table = Table(title="Simulation Summary", border_style="cyan")
        table.add_column("Metric", style="bold white")
        table.add_column("Value", style="bold green")

        table.add_row("Total Turns", str(total_turns))
        table.add_row("Total Individual Moves", str(total_moves))
        table.add_row("Total Drones Delivered", str(len(self.map.drones)))

        self.console.print(table)
