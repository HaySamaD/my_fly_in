"""Responsive ANSI Terminal Visualizer for the Fly-in simulation system.

Provides color-coded terminal dashboards, dynamic width adjustments,
live progress bars, and active zone filtering.
"""

from __future__ import annotations

import re
import shutil
import sys
import textwrap
import time
from typing import TextIO

from src.graph import Graph
from src.models import Zone
from src.simulator import Simulator


class Visualizer:
    """Renders formatted ANSI terminal dashboards for simulations."""

    _COLOR_MAP: dict[str, str] = {
        "black": "\033[30m",
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "purple": "\033[35m",
        "cyan": "\033[36m",
        "gray": "\033[90m",
        "grey": "\033[90m",
        "white": "\033[37m",
    }
    _STYLE_RESET: str = "\033[0m"
    _STYLE_BOLD: str = "\033[1m"
    _STYLE_DIM: str = "\033[2m"
    _STYLE_CYAN: str = "\033[36m"
    _STYLE_GREEN: str = "\033[32m"
    _STYLE_YELLOW: str = "\033[33m"

    def __init__(
        self, graph: Graph, output_stream: TextIO = sys.stdout
    ) -> None:
        """Initialize the visualizer.

        Args:
            graph: The simulation graph.
            output_stream: Output stream for rendering.
        """
        self._graph = graph
        self._stream = output_stream

    def colorize_zone_name(self, zone: Zone) -> str:
        """Wrap zone name in its configured ANSI color code."""
        if not zone.color:
            return zone.name
        color_code = self._COLOR_MAP.get(zone.color.lower(), "")
        if not color_code:
            return zone.name
        return (
            f"{color_code}{self._STYLE_BOLD}{zone.name}{self._STYLE_RESET}"
        )

    def _get_terminal_width(self) -> int:
        """Get current terminal width clamped between 70 and 110 chars."""
        cols = shutil.get_terminal_size((80, 24)).columns
        return max(70, min(cols - 2, 110))

    def _render_progress_bar(
        self, delivered: int, total: int, width: int = 20
    ) -> str:
        """Create a stylized Unicode progress bar."""
        if total <= 0:
            return ""
        pct = delivered / total
        filled = int(round(width * pct))
        bar = " " * filled + " " * (width - filled)
        return (
            f"[{self._STYLE_GREEN}{bar}{self._STYLE_RESET}] "
            f"{delivered}/{total} Delivered ({int(pct * 100)}%)"
        )

    def render_state(self, simulator: Simulator, turn_output: str) -> None:
        """Render a clean dashboard frame for the current turn.

        Args:
            simulator: Live simulator instance.
            turn_output: Output log line for this turn.
        """
        turn = simulator.current_turn
        delivered = self._count_delivered(simulator)
        total = simulator.total_drones
        width = self._get_terminal_width()
        inner_w = width - 4
        sep_line = " " * (width - 2)

        # Header
        self._stream.write(
            f"\n{self._STYLE_BOLD} {sep_line} {self._STYLE_RESET}\n"
        )
        progress_str = self._render_progress_bar(delivered, total, width=16)
        header_content = f" Turn {turn:<4}   {progress_str}"
        pad_hdr = " " * max(0, inner_w - self._visible_len(header_content))
        self._stream.write(f"  {header_content}{pad_hdr}  \n")
        self._stream.write(
            f"{self._STYLE_BOLD} {sep_line} {self._STYLE_RESET}\n"
        )

        # Active Zones (filter out empty nodes)
        active_zones: list[tuple[Zone, list[str]]] = []
        idle_count = 0
        for zone in self._graph.zones.values():
            drones_in_zone = [
                d.name
                for d in simulator._drones.values()
                if d.current_zone == zone.name
                and not d.is_in_transit
                and not (zone.is_end and d.is_delivered)
            ]
            if drones_in_zone:
                active_zones.append((zone, drones_in_zone))
            elif not (zone.is_start or zone.is_end):
                idle_count += 1

        title_zones = (
            f"  {self._STYLE_BOLD}Active Fleet Positions "
            f"({len(active_zones)} Zones):{self._STYLE_RESET}"
        )
        pad_tz = " " * max(0, inner_w - (32 + len(str(len(active_zones)))))
        self._stream.write(f"{title_zones}{pad_tz}  \n")

        for zone, drones in active_zones:
            cap_str = (
                f"{len(drones)}/{zone.max_drones}"
                if not (zone.is_start or zone.is_end)
                else f"{len(drones)}"
            )
            c_name = self.colorize_zone_name(zone)
            drone_str = f"[{', '.join(drones)}]"
            entry = (
                f"    {c_name} ({zone.zone_type.value}, cap: {cap_str}): "
                f"{self._STYLE_CYAN}{drone_str}{self._STYLE_RESET}"
            )
            visible_entry = (
                f"    {zone.name} ({zone.zone_type.value}, "
                f"cap: {cap_str}): {drone_str}"
            )
            if len(visible_entry) > inner_w:
                wrapped_lines = textwrap.wrap(
                    visible_entry, width=inner_w - 4
                )
                for line in wrapped_lines:
                    pad = " " * max(0, inner_w - len(line))
                    self._stream.write(f"  {line}{pad}  \n")
            else:
                pad = " " * max(0, inner_w - self._visible_len(entry))
                self._stream.write(f"  {entry}{pad}  \n")

        if idle_count > 0:
            idle_line = (
                f"  {self._STYLE_DIM}(+{idle_count} idle zones "
                f"currently empty){self._STYLE_RESET}"
            )
            pad_idl = " " * max(0, inner_w - self._visible_len(idle_line))
            self._stream.write(f"  {idle_line}{pad_idl}  \n")

        # In-Transit Links
        in_transit = [
            (
                d.name,
                d.transit_target_zone,
                d.transit_connection.format_name()
                if d.transit_connection
                else "?",
            )
            for d in simulator._drones.values()
            if d.is_in_transit
        ]
        if in_transit:
            self._stream.write(f" {' ' * inner_w} \n")
            title_tr = (
                f"  {self._STYLE_BOLD}In-Transit "
                f"(2-Turn Restricted Links):{self._STYLE_RESET}"
            )
            pad_tr = " " * max(0, inner_w - 38)
            self._stream.write(f"{title_tr}{pad_tr}  \n")
            for d_name, dest, link_name in in_transit:
                transit_str = (
                    f"    {self._STYLE_CYAN}{d_name}{self._STYLE_RESET}   "
                    f"{dest} via {self._STYLE_YELLOW}{link_name}"
                    f"{self._STYLE_RESET}"
                )
                pad = " " * max(0, inner_w - self._visible_len(transit_str))
                self._stream.write(f"  {transit_str}{pad}  \n")

        # Turn Output Command Line
        self._stream.write(
            f"{self._STYLE_BOLD} {sep_line} {self._STYLE_RESET}\n"
        )
        out_display = turn_output if turn_output else "(waiting)"
        wrapped_output = textwrap.wrap(
            f"Output: {out_display}", width=inner_w
        )
        for line in wrapped_output:
            pad = " " * max(0, inner_w - len(line))
            self._stream.write(
                f"  {self._STYLE_BOLD}{line}{self._STYLE_RESET}{pad}  \n"
            )
        self._stream.write(
            f"{self._STYLE_BOLD} {sep_line} {self._STYLE_RESET}\n"
        )
        self._stream.flush()

    def run_animated(
        self, simulator: Simulator, delay: float = 0.25
    ) -> list[str]:
        """Execute simulation with live terminal visualization.

        Args:
            simulator: Simulator instance.
            delay: Delay in seconds between frames.

        Returns:
            List of generated turn output strings.
        """
        outputs: list[str] = []
        while not simulator.is_completed:
            line = simulator.step()
            if line is not None:
                outputs.append(line)
                self.render_state(simulator, line)
                if delay > 0:
                    time.sleep(delay)
        return outputs

    def _count_delivered(self, simulator: Simulator) -> int:
        """Count delivered drones."""
        return sum(1 for d in simulator._drones.values() if d.is_delivered)

    def _visible_len(self, text: str) -> int:
        """Compute printed string length stripped of ANSI sequences."""
        clean = re.sub(r"\033\[[0-9;]*m", "", text)
        return len(clean)
