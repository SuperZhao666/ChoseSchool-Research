from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

from chose_school.infrastructure.database import Database


class SqliteDatabaseBackup:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, destination: Path, force: bool) -> Path:
        if not self._database.path.is_file():
            raise FileNotFoundError(
                f"database does not exist; initialize it before backup: {self._database.path}"
            )
        if destination.exists() and not force:
            raise FileExistsError(
                f"backup already exists; pass --force to replace it: {destination}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            file_descriptor, temporary_name = tempfile.mkstemp(
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
            )
            os.close(file_descriptor)
            temporary_path = Path(temporary_name)
            with self._database.connect_read_only() as source_connection:
                backup_connection = sqlite3.connect(temporary_path)
                try:
                    source_connection.backup(backup_connection)
                finally:
                    backup_connection.close()
            os.replace(temporary_path, destination)
            return destination
        except Exception:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()
            raise
