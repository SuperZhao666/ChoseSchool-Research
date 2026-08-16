from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from chose_school.bootstrap import build_application  # noqa: E402
from chose_school.infrastructure.config import load_settings  # noqa: E402


REAL_ARCHIVE = REPOSITORY_ROOT / "data" / "raw" / "Kimi_Agent_附件对话.zip"


def build_test_application(temporary_directory: Path):
    settings = load_settings(repository_root=REPOSITORY_ROOT)
    settings = replace(
        settings,
        database_path=temporary_directory / "test.sqlite3",
        log_path=temporary_directory / "test.jsonl",
    )
    application = build_application(settings)
    application.database.initialize_database()
    return application, settings
