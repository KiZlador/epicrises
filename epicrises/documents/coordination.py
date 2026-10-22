"""The queue operations needed to coordinate document changes."""

from contextlib import AbstractContextManager
from typing import Protocol


class SessionCoordinator(Protocol):
    lock: AbstractContextManager

    def busy(self, session_id: str) -> bool: ...

    def reset(self, session_id: str) -> None: ...


class ProcessingConflict(Exception):
    pass
