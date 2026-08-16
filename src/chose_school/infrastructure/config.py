from __future__ import annotations

import tomllib
from pathlib import Path

from chose_school.domain.models import Settings


DEFAULT_CONFIG_PATH = Path("config/settings.toml")


def load_settings(
    config_path: Path | None = None,
    repository_root: Path | None = None,
) -> Settings:
    """Load all environment-dependent settings from one explicit file."""

    root = (repository_root or Path(__file__).resolve().parents[3]).resolve()
    path = config_path or root / DEFAULT_CONFIG_PATH
    if not path.is_absolute():
        path = root / path

    with path.open("rb") as config_file:
        config = tomllib.load(config_file)

    database = config["database"]
    logging_config = config["logging"]
    import_config = config["import"]
    strict_exam = config["exam"]["strict_22408"]
    assessment = config["assessment"]
    applicant = config["applicant"]

    return Settings(
        repository_root=root,
        database_path=_resolve_path(root, database["path"]),
        log_path=_resolve_path(root, logging_config["path"]),
        log_level=str(logging_config["level"]),
        busy_timeout_ms=int(database["busy_timeout_ms"]),
        catalog_member_pattern=str(import_config["catalog_member_pattern"]),
        importer_version=str(import_config["importer_version"]),
        max_archive_uncompressed_bytes=int(import_config["max_archive_uncompressed_bytes"]),
        max_member_uncompressed_bytes=int(import_config["max_member_uncompressed_bytes"]),
        max_compression_ratio=float(import_config["max_compression_ratio"]),
        strict_politics_code=str(strict_exam["politics_code"]),
        strict_english_code=str(strict_exam["english_code"]),
        strict_math_code=str(strict_exam["math_code"]),
        strict_professional_code=str(strict_exam["professional_course_code"]),
        minimum_mock_sessions=int(assessment["minimum_sessions"]),
        mock_rolling_window_size=int(assessment["rolling_window_size"]),
        required_machine_durations=tuple(
            int(value) for value in assessment["required_machine_durations"]
        ),
        profile_key=str(applicant["profile_key"]),
        undergraduate_school=str(applicant["undergraduate_school"]),
        undergraduate_major=str(applicant["undergraduate_major"]),
        target_exam_year=int(applicant["target_exam_year"]),
        target_degree_type=str(applicant["target_degree_type"]),
        target_tier=str(applicant["target_tier"]),
    )


def _resolve_path(root: Path, configured_path: str) -> Path:
    path = Path(configured_path)
    return path if path.is_absolute() else root / path
