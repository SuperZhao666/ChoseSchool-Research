from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

from chose_school.business.catalog_service import CatalogService
from chose_school.domain.models import CatalogFilter


EXPORT_COLUMNS = (
    "projection_mode",
    "observation_id",
    "archive_member",
    "source_row_number",
    "school",
    "college",
    "program_code",
    "program_name",
    "direction",
    "campus",
    "training_location",
    "study_mode",
    "training_type_raw",
    "admission_type",
    "degree_type",
    "training_arrangement",
    "admission_year",
    "strict_22408_claim",
    "strict_22408_status",
    "imported_evidence_status",
    "effective_general_exam_quota",
    "retest_cutoff",
    "retest_count",
    "general_exam_admit_count",
    "admit_initial_min",
    "admit_initial_median",
    "admit_initial_mean",
    "initial_exam_weight",
    "retest_weight",
    "machine_test_weight",
    "machine_test_elimination_line",
    "tuition_per_year",
    "study_length_years",
    "first_choice_protection",
    "evidence_grade",
    "official_source",
    "retrieval_date",
    "open_issue_count",
    "notes",
)


class CatalogExportService:
    def __init__(self, catalog_service: CatalogService) -> None:
        self._catalog_service = catalog_service

    def export_catalog(
        self,
        destination: Path,
        force: bool = False,
        excel_safe: bool = False,
        raw_imported: bool = False,
    ) -> int:
        if destination.exists() and not force:
            raise FileExistsError(
                f"destination already exists; pass --force to replace it: {destination}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        rows = self._catalog_service.list_catalog(
            CatalogFilter(limit=100_000, raw_imported=raw_imported)
        )

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8-sig",
                newline="",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as output_file:
                temporary_path = Path(output_file.name)
                writer = csv.DictWriter(output_file, fieldnames=EXPORT_COLUMNS)
                writer.writeheader()
                for row in rows:
                    writer.writerow(
                        {
                            column: _excel_safe(row.get(column))
                            if excel_safe
                            else row.get(column)
                            for column in EXPORT_COLUMNS
                        }
                    )
                output_file.flush()
                os.fsync(output_file.fileno())
            os.replace(temporary_path, destination)
        except Exception:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()
            raise
        return len(rows)


def _excel_safe(value: object) -> object:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value
