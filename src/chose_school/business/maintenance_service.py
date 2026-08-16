from __future__ import annotations

from pathlib import Path
from typing import Protocol

from chose_school.business.ports import IssueResolutionStore
from chose_school.domain.errors import ValidationError


class DatabaseBackup(Protocol):
    def create(self, destination: Path, force: bool) -> Path: ...


class MaintenanceService:
    def __init__(
        self,
        issue_store: IssueResolutionStore,
        database_backup: DatabaseBackup,
    ) -> None:
        self._issue_store = issue_store
        self._database_backup = database_backup

    def resolve_issue(self, issue_id: int, note: str, trace_id: str) -> None:
        if issue_id < 1:
            raise ValidationError("INVALID_ISSUE_ID", "issue_id must be positive")
        if not note.strip():
            raise ValidationError("EMPTY_RESOLUTION_NOTE", "resolution note is required")
        self._issue_store.resolve_issue(issue_id, note.strip(), trace_id)

    def create_backup(self, destination: Path, force: bool = False) -> Path:
        return self._database_backup.create(destination, force)
