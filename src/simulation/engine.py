"""
Simulation engine for execution and capacity-aware batch scheduling.

Executes drone turn-by-turn simulation while strictly enforcing zone
and link capacity limits without deadlock.
"""
from typing import Dict, List, Optional, Tuple

from src.core.enums import ActionType, DroneStatus, ZoneType
from src.core.exceptions import SimulationError
from src.core.models import Connection, Drone, Map, Zone


class SimulationEngine:
    """Core simulation engine controlling turn steps and capacity planning."""

    def __init__(self, map_obj: Map) -> None:
        self.map = map_obj
        self.current_turn: int = 0

    def get_movement_output(
        self, drone: Drone, element: Zone | Connection, action: ActionType
    ) -> str:
        """Format textual movement representation for log outputs."""
        if action in (
            ActionType.MOVE, ActionType.ARRIVE, ActionType.ARRIVE_FINAL
        ):
            assert isinstance(element, Zone)
            return f"{drone.id}-{element.name}"

        if action == ActionType.ENTER_CONNECTION:
            assert isinstance(element, Connection)
            from_name = (
                drone.current_zone.name
                if drone.current_zone else element.from_zone.name
            )
            return f"{drone.id}-{from_name}-{element.to_zone.name}"

        return ""

    def execute_movement(
        self, drone: Drone, element: Zone | Connection, action: ActionType
    ) -> None:
        """Apply state changes of a movement action to the domain model."""
        if action == ActionType.MOVE:
            assert isinstance(element, Zone)
            if drone.current_zone:
                drone.current_zone.remove_drone(drone)
                conn = self.map.find_connection(drone.current_zone, element)
                if conn:
                    conn.add_drone(drone)
                    conn.remove_drone(drone)
            element.add_drone(drone)

        elif action == ActionType.ENTER_CONNECTION:
            assert isinstance(element, Connection)
            if drone.current_zone:
                drone.current_zone.remove_drone(drone)
            element.add_drone(drone)

        elif action == ActionType.ARRIVE:
            assert isinstance(element, Zone)
            for conn in self.map.connections:
                if drone in conn.drones_on_link:
                    conn.remove_drone(drone)
                    break
            element.add_drone(drone)

        elif action == ActionType.ARRIVE_FINAL:
            assert isinstance(element, Zone)
            for conn in self.map.connections:
                if drone in conn.drones_on_link:
                    conn.remove_drone(drone)
            if drone.current_zone:
                drone.current_zone.remove_drone(drone)
            element.add_drone(drone)
            drone.status = DroneStatus.ARRIVED

    def _collect_intended_actions(
        self,
        drone_paths: Dict[
            str, Dict[int, Tuple[Zone | Connection, ActionType]]
        ]
    ) -> List[Tuple[Drone, Zone | Connection, ActionType]]:
        """Collect and sort planned actions for all eligible drones."""
        intended: List[Tuple[Drone, Zone | Connection, ActionType]] = []
        for drone in self.map.drones:
            if drone.status == DroneStatus.IDLE:
                drone.status = DroneStatus.MOVING

            if drone.status in (DroneStatus.MOVING, DroneStatus.WAITING):
                path = drone_paths.get(drone.id, {})
                if drone.current_step in path:
                    element, action = path[drone.current_step]
                    intended.append((drone, element, action))

        intended.sort(key=lambda t: int(t[0].id[1:]))
        return intended

    def simulate_turn(
        self,
        drone_paths: Dict[
            str, Dict[int, Tuple[Zone | Connection, ActionType]]
        ]
    ) -> List[str]:
        """
        Simulate a single turn using capacity planning and batch scheduling.

        Returns a list of formatted movement output strings.
        """
        self.current_turn += 1
        movements: List[str] = []
        intended = self._collect_intended_actions(drone_paths)

        # Capacity tracking dictionaries
        plan_z_in: Dict[str, int] = {}
        plan_z_out: Dict[str, int] = {}
        plan_c_in: Dict[str, int] = {}
        plan_c_out: Dict[str, int] = {}
        plan_c_trans: Dict[str, int] = {}

        to_execute: List[Tuple[Drone, Zone | Connection, ActionType]] = []

        for drone, el, act in intended:
            target_zone, target_conn, source_conn, trans_conn = (
                self._resolve_action_targets(drone, el, act)
            )

            violate = self._check_capacity_violation(
                drone=drone,
                target_zone=target_zone,
                target_conn=target_conn,
                source_conn=source_conn,
                trans_conn=trans_conn,
                p_z_in=plan_z_in,
                p_z_out=plan_z_out,
                p_c_in=plan_c_in,
                p_c_out=plan_c_out,
                p_c_trans=plan_c_trans,
            )

            if not violate:
                self._update_planned_counters(
                    drone=drone,
                    target_zone=target_zone,
                    target_conn=target_conn,
                    source_conn=source_conn,
                    trans_conn=trans_conn,
                    p_z_in=plan_z_in,
                    p_z_out=plan_z_out,
                    p_c_in=plan_c_in,
                    p_c_out=plan_c_out,
                    p_c_trans=plan_c_trans,
                )
                to_execute.append((drone, el, act))
            else:
                drone.status = DroneStatus.WAITING

        for drone, el, act in to_execute:
            self.execute_movement(drone, el, act)
            output = self.get_movement_output(drone, el, act)
            if output:
                movements.append(output)
            drone.current_step += 1
            if act != ActionType.ARRIVE_FINAL:
                drone.status = DroneStatus.MOVING

        return movements

    def _resolve_action_targets(
        self, drone: Drone, el: Zone | Connection, act: ActionType
    ) -> Tuple[
        Optional[Zone],
        Optional[Connection],
        Optional[Connection],
        Optional[Connection]
    ]:
        """Resolve involved zone and connection targets for an action."""
        target_zone: Optional[Zone] = None
        target_conn: Optional[Connection] = None
        source_conn: Optional[Connection] = None
        trans_conn: Optional[Connection] = None

        if (
            act == ActionType.ARRIVE_FINAL
            and isinstance(el, Zone)
            and el.zone_type == ZoneType.RESTRICTED
        ):
            for c in self.map.connections:
                if drone in c.drones_on_link:
                    source_conn = c
                    break

        if act in (ActionType.MOVE, ActionType.ARRIVE_FINAL):
            assert isinstance(el, Zone)
            target_zone = el
            if drone.current_zone:
                trans_conn = self.map.find_connection(drone.current_zone, el)

        elif act == ActionType.ENTER_CONNECTION:
            assert isinstance(el, Connection)
            target_conn = el

        elif act == ActionType.ARRIVE:
            assert isinstance(el, Zone)
            target_zone = el
            for c in self.map.connections:
                if drone in c.drones_on_link:
                    source_conn = c
                    break

        return target_zone, target_conn, source_conn, trans_conn

    def _check_capacity_violation(
        self,
        drone: Drone,
        target_zone: Optional[Zone],
        target_conn: Optional[Connection],
        source_conn: Optional[Connection],
        trans_conn: Optional[Connection],
        p_z_in: Dict[str, int],
        p_z_out: Dict[str, int],
        p_c_in: Dict[str, int],
        p_c_out: Dict[str, int],
        p_c_trans: Dict[str, int],
    ) -> bool:
        """Check if action violates zone or connection capacity limits."""
        # Source zone check
        if drone.current_zone:
            z = drone.current_zone
            cur = len(z.drones_present)
            pi = p_z_in.get(z.name, 0)
            po = p_z_out.get(z.name, 0)
            if cur - (po + 1) + pi > z.max_drones:
                return True

        # Target zone check
        if target_zone:
            cur = len(target_zone.drones_present)
            pi = p_z_in.get(target_zone.name, 0)
            po = p_z_out.get(target_zone.name, 0)
            if cur - po + (pi + 1) > target_zone.max_drones:
                return True

        # Transient connection check
        if trans_conn:
            cid = str(id(trans_conn))
            cur = len(trans_conn.drones_on_link)
            pi, po = p_c_in.get(cid, 0), p_c_out.get(cid, 0)
            ptr = p_c_trans.get(cid, 0)
            if (cur - po + pi + ptr + 1) > trans_conn.max_links:
                return True

        # Target connection check
        if target_conn:
            cid = str(id(target_conn))
            cur = len(target_conn.drones_on_link)
            pi, po = p_c_in.get(cid, 0), p_c_out.get(cid, 0)
            ptr = p_c_trans.get(cid, 0)
            if (cur - po + (pi + 1) + ptr) > target_conn.max_links:
                return True

        # Source connection check
        if source_conn:
            cid = str(id(source_conn))
            cur = len(source_conn.drones_on_link)
            pi, po = p_c_in.get(cid, 0), p_c_out.get(cid, 0)
            ptr = p_c_trans.get(cid, 0)
            if (cur - (po + 1) + pi + ptr) > source_conn.max_links:
                return True

        return False

    def _update_planned_counters(
        self,
        drone: Drone,
        target_zone: Optional[Zone],
        target_conn: Optional[Connection],
        source_conn: Optional[Connection],
        trans_conn: Optional[Connection],
        p_z_in: Dict[str, int],
        p_z_out: Dict[str, int],
        p_c_in: Dict[str, int],
        p_c_out: Dict[str, int],
        p_c_trans: Dict[str, int],
    ) -> None:
        """Increment planning capacity tracking counters."""
        if drone.current_zone:
            zn = drone.current_zone.name
            p_z_out[zn] = p_z_out.get(zn, 0) + 1
        if target_zone:
            zn = target_zone.name
            p_z_in[zn] = p_z_in.get(zn, 0) + 1
        if trans_conn:
            cid = str(id(trans_conn))
            p_c_trans[cid] = p_c_trans.get(cid, 0) + 1
        if target_conn:
            cid = str(id(target_conn))
            p_c_in[cid] = p_c_in.get(cid, 0) + 1
        if source_conn:
            cid = str(id(source_conn))
            p_c_out[cid] = p_c_out.get(cid, 0) + 1

    def is_finished(self) -> bool:
        """Check if all drones arrived at the destination hub."""
        return all(
            drone.status == DroneStatus.ARRIVED for drone in self.map.drones
        )

    def run_all(
        self,
        drone_paths: Dict[
            str, Dict[int, Tuple[Zone | Connection, ActionType]]
        ],
        max_turns: int = 100,
    ) -> List[str]:
        """Run complete simulation until completion or max_turns threshold."""
        all_movements: List[str] = []
        while not self.is_finished():
            movements = self.simulate_turn(drone_paths)
            if movements:
                all_movements.append(" ".join(movements))
            else:
                all_movements.append("")

            if self.current_turn > max_turns:
                raise SimulationError(
                    "Simulation exceeded maximum allowed threshold "
                    f"({max_turns} turns)"
                )

        return all_movements
