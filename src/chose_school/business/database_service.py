from __future__ import annotations

from pathlib import Path

from chose_school.business.ports import SchemaManager
from chose_school.domain.errors import StateConflictError


class DatabaseAdministrationService:
    def __init__(self, schema_manager: SchemaManager) -> None:
        self._schema_manager = schema_manager

    @property
    def database_path(self) -> Path:
        return self._schema_manager.path

    def initialize_database(self) -> dict[str, object]:
        applied_migrations = self._schema_manager.migrate()
        return {
            "database": str(self.database_path),
            "applied_migrations": applied_migrations,
            "status": "ready",
        }

    def require_current_schema(self) -> None:
        status = self._schema_manager.inspect_schema()
        if status.is_current:
            return
        if status.mismatch_reason is not None:
            raise StateConflictError(
                "DATABASE_SCHEMA_MISMATCH",
                f"database schema does not match the migration ledger: "
                f"{status.mismatch_reason}",
            )
        current_version = status.current_version or 0
        raise StateConflictError(
            "DATABASE_MIGRATION_REQUIRED",
            f"database schema is at version {current_version}; version "
            f"{status.required_version} is required. Run 'python manage.py init' first.",
            {
                "current_version": current_version,
                "required_version": status.required_version,
                "pending_versions": list(status.pending_versions),
            },
        )
