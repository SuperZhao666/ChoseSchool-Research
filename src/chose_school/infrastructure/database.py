from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from chose_school.business.ports import SchemaStatus


class MigrationChecksumError(RuntimeError):
    pass


class Database:
    """Owns SQLite connections and schema migration, not business queries."""

    def __init__(self, path: Path, busy_timeout_ms: int = 5000) -> None:
        self._path = path
        self._busy_timeout_ms = busy_timeout_ms

    @property
    def path(self) -> Path:
        return self._path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms}")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def connect_read_only(self) -> Iterator[sqlite3.Connection]:
        if not self._path.is_file():
            raise FileNotFoundError(f"database does not exist: {self._path}")
        connection = sqlite3.connect(
            f"{self._path.resolve().as_uri()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms}")
        connection.execute("PRAGMA query_only = ON")
        try:
            yield connection
        finally:
            connection.close()

    def inspect_schema(self) -> SchemaStatus:
        migration_paths = self._migration_paths()
        expected = {
            int(path.name.split("_", 1)[0]): (
                path.name,
                hashlib.sha256(
                    path.read_text(encoding="utf-8").encode("utf-8")
                ).hexdigest(),
            )
            for path in migration_paths
        }
        required_version = max(expected, default=0)
        all_versions = tuple(sorted(expected))
        if not self._path.is_file():
            return SchemaStatus(
                is_current=False,
                current_version=None,
                required_version=required_version,
                pending_versions=all_versions,
            )

        with self.connect_read_only() as connection:
            has_ledger = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table' AND name = 'schema_migrations'
                """
            ).fetchone()
            if has_ledger is None:
                return SchemaStatus(
                    is_current=False,
                    current_version=None,
                    required_version=required_version,
                    pending_versions=all_versions,
                )
            applied_rows = connection.execute(
                """
                SELECT version, filename, checksum
                FROM schema_migrations
                ORDER BY version
                """
            ).fetchall()

        applied_versions = {int(row["version"]) for row in applied_rows}
        current_version = max(applied_versions, default=0)
        for row in applied_rows:
            version = int(row["version"])
            expected_identity = expected.get(version)
            if expected_identity is None:
                return SchemaStatus(
                    is_current=False,
                    current_version=current_version,
                    required_version=required_version,
                    pending_versions=(),
                    mismatch_reason=f"unknown applied migration version {version}",
                )
            if (row["filename"], row["checksum"]) != expected_identity:
                return SchemaStatus(
                    is_current=False,
                    current_version=current_version,
                    required_version=required_version,
                    pending_versions=(),
                    mismatch_reason=f"migration {version} filename or checksum differs",
                )

        pending_versions = tuple(sorted(set(expected) - applied_versions))
        return SchemaStatus(
            is_current=not pending_versions,
            current_version=current_version,
            required_version=required_version,
            pending_versions=pending_versions,
        )

    def migrate(self) -> list[int]:
        applied_now: list[int] = []
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    filename TEXT NOT NULL UNIQUE,
                    checksum TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

            applied = {
                int(row["version"]): row["checksum"]
                for row in connection.execute(
                    "SELECT version, checksum FROM schema_migrations"
                )
            }

            for migration_path in self._migration_paths():
                version = int(migration_path.name.split("_", 1)[0])
                sql = migration_path.read_text(encoding="utf-8")
                checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
                if version in applied:
                    if applied[version] != checksum:
                        raise MigrationChecksumError(
                            f"Migration {migration_path.name} changed after application"
                        )
                    continue

                applied_at = datetime.now(timezone.utc).isoformat()
                safe_filename = migration_path.name.replace("'", "''")
                script = (
                    "BEGIN IMMEDIATE;\n"
                    f"{sql}\n"
                    "INSERT INTO schema_migrations(version, filename, checksum, applied_at) "
                    f"VALUES ({version}, '{safe_filename}', '{checksum}', '{applied_at}');\n"
                    "COMMIT;"
                )
                try:
                    connection.executescript(script)
                except Exception:
                    connection.rollback()
                    raise
                applied_now.append(version)
        return applied_now

    @staticmethod
    def _migration_paths() -> list[Path]:
        migration_dir = Path(__file__).resolve().parent / "migrations"
        return sorted(migration_dir.glob("[0-9][0-9][0-9]_*.sql"))
