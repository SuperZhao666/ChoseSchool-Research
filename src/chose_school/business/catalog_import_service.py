from __future__ import annotations

import logging
import time
from pathlib import Path

from chose_school.business.ports import CatalogArchiveReader, CatalogImportStore
from chose_school.domain.catalog_normalizer import normalize_catalog_row
from chose_school.domain.models import ImportResult


LOGGER = logging.getLogger(__name__)


class CatalogImportService:
    def __init__(
        self,
        archive_reader: CatalogArchiveReader,
        import_store: CatalogImportStore,
        importer_version: str,
    ) -> None:
        self._archive_reader = archive_reader
        self._import_store = import_store
        self._importer_version = importer_version

    def import_archive(
        self,
        archive_path: Path,
        batch_id: str,
        trace_id: str,
    ) -> ImportResult:
        started = time.perf_counter()
        source_hash = self._archive_reader.source_sha256(archive_path)
        duplicate_of = self._import_store.find_successful_batch(
            source_hash,
            self._importer_version,
        )
        if duplicate_of is not None:
            result = self._import_store.record_duplicate_batch(
                batch_id=batch_id,
                trace_id=trace_id,
                archive_path=archive_path,
                source_sha256=source_hash,
                importer_version=self._importer_version,
                duplicate_of=duplicate_of,
            )
            self._log_result(result, trace_id, started)
            return result

        self._import_store.start_batch(
            batch_id=batch_id,
            trace_id=trace_id,
            archive_path=archive_path,
            source_sha256=source_hash,
            importer_version=self._importer_version,
        )
        try:
            archive = self._archive_reader.read(archive_path)
            normalized_rows = {
                (source_file.archive_member, raw_row.row_number): normalize_catalog_row(
                    raw_row
                )
                for source_file in archive.source_files
                for raw_row in source_file.rows
            }
            result = self._import_store.persist_import(
                batch_id=batch_id,
                source_sha256=source_hash,
                archive=archive,
                normalized_rows=normalized_rows,
            )
        except Exception as error:
            self._import_store.mark_batch_failed(batch_id, str(error))
            LOGGER.exception(
                "catalog import failed",
                extra={
                    "trace_id": trace_id,
                    "operation": "catalog_import",
                    "status": "failed",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            raise

        self._log_result(result, trace_id, started)
        return result

    def _log_result(
        self,
        result: ImportResult,
        trace_id: str,
        started: float,
    ) -> None:
        LOGGER.info(
            "catalog import completed",
            extra={
                "trace_id": trace_id,
                "operation": "catalog_import",
                "status": result.status,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
