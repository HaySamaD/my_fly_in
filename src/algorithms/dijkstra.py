"""
Dijkstra's shortest-path routing algorithm for Fly-in drones.

Calculates optimal paths while handling zone costs, restricted delay turns,
and priority zone preferences.
"""
import heapq
from typing import Dict, List, Tuple

from src.core.enums import ActionType, ZoneType
from src.core.exceptions import PathfindingError
from src.core.models import Connection, Map, Zone


class DijkstraRouter:
    """
    Pathfinding router using weighted Dijkstra with priority tie-breaking.
    """

    def __init__(self, map_obj: Map) -> None:
        self.map = map_obj

    def get_zone_cost(self, zone: Zone) -> int:
        """
        Return turn cost for entering a zone.

        Restricted zones require 2 turns; normal and priority cost 1 turn.
        """
        if zone.zone_type == ZoneType.RESTRICTED:
            return 2
        return 1

    def get_priority_score(self, zone: Zone) -> int:
        """
        Return priority preference score.

        Priority zones score 0 (preferred), normal zones score 1.
        """
        if zone.zone_type == ZoneType.PRIORITY:
            return 0
        return 1

    def find_shortest_path(self, start: Zone, goal: Zone) -> List[Zone]:
        """
        Find optimal zone sequence from start to goal hub.

        Excludes BLOCKED zones and prioritizes minimal total turn cost.
        """
        # PQ tuple: (cost, prio_score, counter, current_zone, path)
        pq: List[Tuple[int, int, int, Zone, List[Zone]]] = []
        counter = 0
        heapq.heappush(pq, (0, 0, counter, start, [start]))

        best_known: Dict[str, Tuple[int, int]] = {start.name: (0, 0)}

        while pq:
            cost, prio_score, _, curr, path = heapq.heappop(pq)

            if curr == goal:
                return path

            best_c, best_p = best_known.get(
                curr.name, (float("inf"), float("inf"))
            )
            if (cost, prio_score) > (best_c, best_p):
                continue

            for neighbor in self.map.neighbors(curr):
                new_cost = cost + self.get_zone_cost(neighbor)
                new_prio = prio_score + self.get_priority_score(neighbor)

                old_best = best_known.get(neighbor.name)
                if old_best is None or (new_cost, new_prio) < old_best:
                    best_known[neighbor.name] = (new_cost, new_prio)
                    counter += 1
                    heapq.heappush(
                        pq,
                        (
                            new_cost,
                            new_prio,
                            counter,
                            neighbor,
                            path + [neighbor],
                        ),
                    )

        raise PathfindingError(
            f"No valid path found from '{start.name}' to '{goal.name}'"
        )

    def build_indexed_actions(
        self, zone_path: List[Zone]
    ) -> Dict[int, Tuple[Zone | Connection, ActionType]]:
        """Convert a sequence of zones into step-indexed simulation actions."""
        if not zone_path:
            return {}

        indexed_path: Dict[int, Tuple[Zone | Connection, ActionType]] = {}
        step = 0

        for i in range(len(zone_path) - 1):
            curr = zone_path[i]
            nxt = zone_path[i + 1]
            conn = self.map.find_connection(curr, nxt)

            if conn is None:
                raise PathfindingError(
                    f"Missing link between '{curr.name}' and '{nxt.name}'"
                )

            is_final = i == len(zone_path) - 2

            if nxt.zone_type == ZoneType.RESTRICTED:
                indexed_path[step] = (conn, ActionType.ENTER_CONNECTION)
                step += 1
                act = (
                    ActionType.ARRIVE_FINAL if is_final else ActionType.ARRIVE)
                indexed_path[step] = (nxt, act)
                step += 1
            else:
                act = ActionType.ARRIVE_FINAL if is_final else ActionType.MOVE
                indexed_path[step] = (nxt, act)
                step += 1

        return indexed_path
