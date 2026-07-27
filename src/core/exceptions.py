"""
Custom exception hierarchy for the fly-in routing engine.
Provides detailed context, line numbers, and structured error reporting.
"""
from typing import Optional


class FlyInError(Exception):
    """Base exception class for all Fly-in system errors."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return f"[FlyInError] {self.message}"


class MapParseError(FlyInError):
    """Raised when parsing map text files fails due to syntax
    or semantic errors.
    """
    def __init__(self,
                 message: str,
                 line_num: Optional[int] = None,
                 line_content: Optional[str] = None) -> None:
        self.line_num = line_num
        self.line_content = line_content
        detail = f"Line {line_num}: {message}" if line_num else message
        if line_content:
            detail += f" -> '{line_content}'"
        super().__init__(detail)


class MapValidationError(FlyInError):
    """Raised when map structure violates connectivity or capacity rules."""
    pass


class PathfindingError(FlyInError):
    """Raised when no valid path exists between start and goal hubs."""
    pass


class SimulationError(FlyInError):
    """Raised when simulation hits a dead-lock or exceeds allowed turns."""
    pass
