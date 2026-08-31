"""Turn-based Space-Time routing and reservation engine for Fly-in.

Implements Space-Time A* search with multi-path load balancing and dynamic
reservations to coordinate collision-free, distributed fleet flight schedules.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import heapq
import math

from src.graph import Graph
from src.models import Connection, Zone, ZoneType


@dataclass(slots=True, frozen=True)
class DroneAction:
    """Represents a discrete action taken by a drone on a specific turn."""

    turn: int
    drone_id: int
    destination_zone: str
    is_connection_transit: bool = False
    connection_name: str | None = None

    @property
    def output_representation(self) -> str:
        """Format token for turn log output (e.g. 'D1-roof1')."""
        if self.is_connection_transit and self.connection_name is not None:
            return f"D{self.drone_id}-{self.connection_name}"
        return f"D{self.drone_id}-{self.destination_zone}"


@dataclass(slots=True)
class ScheduledPlan:
    """Complete flight plan for an individual drone across time."""

    drone_id: int
    arrival_turn: int
    actions: list[DroneAction]


class ReservationTable:
    """Space-time reservation schedule tracking zone and link occupancies."""

    def __init__(self) -> None:
        """Initialize empty space-time reservation registries."""
        # (zone_name, turn) -> number of drones occupying zone at turn
        self._zone_occupancy: dict[tuple[str, int], int] = defaultdict(int)
        # (canonical_edge, turn) -> drones traversing link during turn
        self._link_occupancy: dict[
            tuple[tuple[str, str], int], int
        ] = defaultdict(int)
        # Global cumulative usage count to encourage multi-path spreading
        self._edge_total_usage: dict[tuple[str, str], int] = defaultdict(int)

    def is_zone_available(self, zone: Zone, turn: int) -> bool:
        """Check if a zone has available capacity at a specific turn."""
        if zone.is_start or zone.is_end:
            return True
        current_count = self._zone_occupancy[(zone.name, turn)]
        return current_count < zone.max_drones

    def is_link_available(self, connection: Connection, turn: int) -> bool:
        """Check if a connection link has capacity at a specific turn."""
        key = (connection.canonical_pair, turn)
        return self._link_occupancy[key] < connection.max_link_capacity

    def reserve_zone(self, zone: Zone, turn: int) -> None:
        """Reserve a zone slot at a specific turn."""
        if not (zone.is_start or zone.is_end):
            self._zone_occupancy[(zone.name, turn)] += 1

    def reserve_link(self, connection: Connection, turn: int) -> None:
        """Reserve a connection slot for transit during a specific turn."""
        self._link_occupancy[(connection.canonical_pair, turn)] += 1
        self._edge_total_usage[connection.canonical_pair] += 1

    def get_edge_load(self, connection: Connection) -> int:
        """Return cumulative historical usage of an edge."""
        return self._edge_total_usage[connection.canonical_pair]


class SpaceTimeRouter:
    """Space-time pathfinder and multi-path fleet coordinator."""

    def __init__(self, graph: Graph) -> None:
        """Initialize router with graph topology and precompute heuristics.

        Args:
            graph: The simulation graph network.
        """
        self._graph = graph
        self._heuristic_cache: dict[str, float] = {}
        self._precompute_admissible_heuristics()

    def _precompute_admissible_heuristics(self) -> None:
        """Compute backward Dijkstra distances from end hub to all zones."""
        end_zone = self._graph.end_zone
        queue: list[tuple[float, str]] = [(0.0, end_zone.name)]
        self._heuristic_cache[end_zone.name] = 0.0

        while queue:
            dist, current_name = heapq.heappop(queue)
            if dist > self._heuristic_cache.get(current_name, math.inf):
                continue
            current_zone = self._graph.get_zone(current_name)
            step_cost = (
                2.0 if current_zone.zone_type == ZoneType.RESTRICTED else 1.0
            )
            for neighbor_zone, _ in self._graph.get_neighbors(current_name):
                n_name = neighbor_zone.name
                new_dist = dist + step_cost
                if new_dist < self._heuristic_cache.get(n_name, math.inf):
                    self._heuristic_cache[n_name] = new_dist
                    heapq.heappush(queue, (new_dist, n_name))

    def _get_heuristic(self, zone_name: str) -> float:
        """Return the estimated turn distance from zone to end hub."""
        return self._heuristic_cache.get(zone_name, float("inf"))

    def schedule_fleet(self, nb_drones: int) -> list[ScheduledPlan]:
        """Generate conflict-free flight plans distributed across paths.

        Args:
            nb_drones: Number of drones to route from start to destination.

        Returns:
            A list of ScheduledPlan instances for all drones.

        Raises:
            RuntimeError: If a path cannot be scheduled for any drone.
        """
        reservation_table = ReservationTable()
        fleet_plans: list[ScheduledPlan] = []

        for drone_id in range(1, nb_drones + 1):
            plan = self._find_space_time_path(drone_id, reservation_table)
            if plan is None:
                raise RuntimeError(
                    f"Failed to find a viable schedule for Drone D{drone_id}"
                )
            self._commit_plan(plan, reservation_table)
            fleet_plans.append(plan)

        return fleet_plans

    def _find_space_time_path(
        self, drone_id: int, table: ReservationTable
    ) -> ScheduledPlan | None:
        """Find earliest arrival schedule distributing across multiple paths.

        Args:
            drone_id: Numeric identifier of the drone.
            table: Current reservation table containing existing bookings.

        Returns:
            ScheduledPlan with discrete actions, or None if unreachable.
        """
        start_name = self._graph.start_zone.name
        end_name = self._graph.end_zone.name

        counter = 0
        initial_h = self._get_heuristic(start_name)
        # Tuple: (f_score, arrival_turn, counter, curr_name, actions)
        queue: list[tuple[float, int, int, str, list[DroneAction]]] = [
            (initial_h, 0, counter, start_name, [])
        ]
        visited_states: set[tuple[str, int]] = set()
        max_search_horizon = 500

        while queue:
            est_total, turn, _, curr_name, actions = heapq.heappop(queue)
            if curr_name == end_name:
                return ScheduledPlan(
                    drone_id=drone_id,
                    arrival_turn=turn,
                    actions=actions,
                )

            state_key = (curr_name, turn)
            if state_key in visited_states:
                continue
            visited_states.add(state_key)

            if turn >= max_search_horizon:
                continue

            curr_zone = self._graph.get_zone(curr_name)

            # Option 1: Move to an adjacent traversable neighbor
            for neighbor_zone, conn in self._graph.get_neighbors(curr_name):
                n_name = neighbor_zone.name
                # Multi-path load-balancing tie breaker:
                # Drones prefer unused or less-trafficked links over waiting
                edge_congestion = table.get_edge_load(conn) * 0.001

                if neighbor_zone.zone_type == ZoneType.RESTRICTED:
                    transit_turn = turn + 1
                    arrival_turn = turn + 2
                    if not table.is_link_available(conn, transit_turn):
                        continue
                    if not table.is_zone_available(
                        neighbor_zone, arrival_turn
                    ):
                        continue
                    transit_action = DroneAction(
                        turn=transit_turn,
                        drone_id=drone_id,
                        destination_zone=n_name,
                        is_connection_transit=True,
                        connection_name=conn.format_name(),
                    )
                    landing_action = DroneAction(
                        turn=arrival_turn,
                        drone_id=drone_id,
                        destination_zone=n_name,
                        is_connection_transit=False,
                    )
                    next_actions = actions + [transit_action, landing_action]
                    next_turn = arrival_turn
                    priority_bias = 0.0
                else:
                    arrival_turn = turn + 1
                    if not table.is_link_available(conn, arrival_turn):
                        continue
                    if not table.is_zone_available(
                        neighbor_zone, arrival_turn
                    ):
                        continue
                    move_action = DroneAction(
                        turn=arrival_turn,
                        drone_id=drone_id,
                        destination_zone=n_name,
                        is_connection_transit=False,
                    )
                    next_actions = actions + [move_action]
                    next_turn = arrival_turn
                    is_prio = neighbor_zone.zone_type == ZoneType.PRIORITY
                    priority_bias = -0.1 if is_prio else 0.0

                new_g = float(next_turn)
                new_h = self._get_heuristic(n_name)
                f_score = new_g + new_h + priority_bias + edge_congestion
                counter += 1
                heapq.heappush(
                    queue,
                    (f_score, next_turn, counter, n_name, next_actions),
                )

            # Option 2: Strategic waiting in the current zone
            wait_turn = turn + 1
            if curr_zone.is_start or table.is_zone_available(
                curr_zone, wait_turn
            ):
                wait_g = float(wait_turn)
                wait_h = self._get_heuristic(curr_name)
                # Slight wait penalty so drone branches into alternate
                # available paths immediately rather than waiting idle
                wait_penalty = 0.01 if curr_zone.is_start else 0.0
                counter += 1
                heapq.heappush(
                    queue,
                    (
                        wait_g + wait_h + wait_penalty,
                        wait_turn,
                        counter,
                        curr_name,
                        list(actions),
                    ),
                )
        return None

    def _commit_plan(
        self, plan: ScheduledPlan, table: ReservationTable
    ) -> None:
        """Register all planned actions into the reservation table."""
        curr_zone_name = self._graph.start_zone.name
        last_turn = 0
        for action in plan.actions:
            # Reserve idle wait turns in current zone
            for w_turn in range(last_turn + 1, action.turn):
                zone = self._graph.get_zone(curr_zone_name)
                table.reserve_zone(zone, w_turn)

            if action.is_connection_transit:
                conn = self._graph.get_connection(
                    curr_zone_name, action.destination_zone
                )
                if conn is not None:
                    table.reserve_link(conn, action.turn)
            else:
                is_landing = any(
                    a.is_connection_transit
                    and a.turn == action.turn - 1
                    and a.destination_zone == action.destination_zone
                    for a in plan.actions
                )
                if not is_landing:
                    conn = self._graph.get_connection(
                        curr_zone_name, action.destination_zone
                    )
                    if conn is not None:
                        table.reserve_link(conn, action.turn)

                dest_zone = self._graph.get_zone(action.destination_zone)
                table.reserve_zone(dest_zone, action.turn)
                curr_zone_name = action.destination_zone

            last_turn = action.turn
