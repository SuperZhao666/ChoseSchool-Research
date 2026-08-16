from __future__ import annotations

from typing import Any, Mapping


class ChoseSchoolError(Exception):
    """Base class for expected, user-actionable failures."""

    def __init__(
        self,
        error_code: str,
        message: str,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.context = dict(context or {})


class ValidationError(ChoseSchoolError):
    pass


class EntityNotFoundError(ChoseSchoolError):
    pass


class StateConflictError(ChoseSchoolError):
    pass
