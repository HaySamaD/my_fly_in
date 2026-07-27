"""
Domain enumerations for the Fly-in simulation engine.

Defines zone types, drone states, and simulation action step identifiers.
"""
from enum import Enum


class ZoneType(str, Enum):
    """Supported zone classification types."""

    NORMAL = "normal"
    RESTRICTED = "restricted"
    PRIORITY = "priority"
    BLOCKED = "blocked"


class DroneStatus(str, Enum):
    """Execution status of an individual drone."""

    IDLE = "idle"
    MOVING = "moving"
    WAITING = "waiting"
    ARRIVED = "arrived"


class ActionType(str, Enum):
    """Discrete simulation actions performed during a turn step."""

    MOVE = "move"
    ENTER_CONNECTION = "enter_connection"
    ARRIVE = "arrive"
    ARRIVE_FINAL = "arrive_final"
