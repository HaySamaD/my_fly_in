"""Discrete-event simulation engine for Fly-in.

Executes turn-by-turn drone flight schedules, enforces capacity invariants,
and generates standardized output streams.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from src.graph import Graph
from src.models import Connection, Drone
from src.router import DroneAction, ScheduledPlan


class SimulationError(Exception):
    """Exception raised when a simulation constraint is violated."""


class Simulator:
    """Turn-by-turn simulation engine executing and validating schedules."""

    def __init__(self, graph: Graph, plans: Sequence[ScheduledPlan]) -> None:
        """Initialize the simulator with graph topology and flight plans.

        Args:
            graph: The simulation graph.
            plans: Flight plans for all drones.
        """
        self._graph = graph
        self._plans = plans
        self._current_turn: int = 0
        self._is_completed: bool = False

        # Map drone_id -> Drone runtime state
        self._drones: dict[int, Drone] = {
            plan.drone_id: Drone(
                drone_id=plan.drone_id,
                current_zone=self._graph.start_zone.name,
            )
            for plan in plans
        }

        # Map turn -> list of DroneAction
        self._action_timeline: dict[int, list[DroneAction]] = defaultdict(list)
        self._max_scheduled_turn: int = 0
        self._index_actions()

    def _index_actions(self) -> None:
        """Index planned actions into discrete turns for execution."""
        for plan in self._plans:
            for action in plan.actions:
                self._action_timeline[action.turn].append(action)
                if action.turn > self._max_scheduled_turn:
                    self._max_scheduled_turn = action.turn

    @property
    def current_turn(self) -> int:
        """Return the current simulation turn number."""
        return self._current_turn

    @property
    def is_completed(self) -> bool:
        """Return True if all drones have reached the end zone."""
        return self._is_completed

    @property
    def total_drones(self) -> int:
        """Return total number of drones in the simulation."""
        return len(self._drones)

    def step(self) -> str | None:
        """Advance the simulation by one discrete turn.

        Returns:
            Formatted string for turn, or None if simulation is finished.

        Raises:
            SimulationError: If any capacity or transit constraint is violated.
        """
        if self._is_completed:
            return None

        self._current_turn += 1
        turn_actions = self._action_timeline.get(self._current_turn, [])
        output_tokens: list[str] = []

        # Track link traversals to verify max_link_capacity
        link_traversals: dict[tuple[str, str], int] = defaultdict(int)

        # 1. Update transit states and apply planned movements
        for action in turn_actions:
            drone = self._drones[action.drone_id]
            if action.is_connection_transit:
                # Entering 2-turn restricted transit
                conn = self._graph.get_connection(
                    drone.current_zone, action.destination_zone
                )
                if conn is None:
                    raise SimulationError(
                        f"Turn {self._current_turn}: No connection between "
                        f"'{drone.current_zone}' and "
                        f"'{action.destination_zone}'"
                    )
                link_traversals[conn.canonical_pair] += 1
                self._verify_link_capacity(
                    conn, link_traversals[conn.canonical_pair]
                )
                drone.transit_target_zone = action.destination_zone
                drone.transit_connection = conn
                drone.remaining_transit_turns = 1
            else:
                # Completing 1-turn move or landing from 2-turn transit
                if drone.is_in_transit:
                    drone.remaining_transit_turns = 0
                    drone.transit_connection = None
                else:
                    # Traversed standard link during this turn
                    conn = self._graph.get_connection(
                        drone.current_zone, action.destination_zone
                    )
                    if conn is not None:
                        link_traversals[conn.canonical_pair] += 1
                        self._verify_link_capacity(
                            conn, link_traversals[conn.canonical_pair]
                        )

                drone.current_zone = action.destination_zone
                drone.transit_target_zone = None
                if drone.current_zone == self._graph.end_zone.name:
                    drone.is_delivered = True

            output_tokens.append(action.output_representation)

        # 2. Verify all active zone capacities after turn movements complete
        self._verify_zone_occupancies()

        # 3. Check termination status
        all_delivered = all(d.is_delivered for d in self._drones.values())
        if all_delivered or self._current_turn >= self._max_scheduled_turn:
            self._is_completed = True

        return " ".join(output_tokens) if output_tokens else ""

    def run_all(self) -> list[str]:
        """Execute the entire simulation from start to completion.

        Returns:
            List of formatted output lines for every active turn.
        """
        output_lines: list[str] = []
        while not self._is_completed:
            line = self.step()
            if line:
                output_lines.append(line)
        return output_lines

    def _verify_link_capacity(
        self, conn: Connection, current_count: int
    ) -> None:
        """Enforce connection link capacity limits."""
        if current_count > conn.max_link_capacity:
            raise SimulationError(
                f"Turn {self._current_turn}: Link '{conn.format_name()}' "
                f"exceeded capacity ({current_count} > "
                f"{conn.max_link_capacity})"
            )

    def _verify_zone_occupancies(self) -> None:
        """Enforce zone capacity constraints for all non-terminal hubs."""
        zone_counts: dict[str, int] = defaultdict(int)
        for drone in self._drones.values():
            if not drone.is_in_transit and not drone.is_delivered:
                zone_counts[drone.current_zone] += 1

        for zone_name, count in zone_counts.items():
            zone = self._graph.get_zone(zone_name)
            if not zone.is_start and not zone.is_end:
                if count > zone.max_drones:
                    raise SimulationError(
                        f"Turn {self._current_turn}: Zone '{zone.name}' "
                        f"exceeded capacity ({count} > {zone.max_drones})"
                    )

    def get_summary_statistics(self) -> dict[str, float | int]:
        """Compute simulation performance metrics."""
        return {
            "total_turns": self._current_turn,
            "total_drones": len(self._drones),
            "average_turns_per_drone": (
                sum(p.arrival_turn for p in self._plans) / len(self._plans)
                if self._plans
                else 0.0
            ),
        }
