from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", None),
            "user_id": getattr(record, "user_id", None),
            "operation": getattr(record, "operation", None),
            "status": getattr(record, "status", None),
            "duration_ms": getattr(record, "duration_ms", None),
            "result_count": getattr(record, "result_count", None),
            "error_code": getattr(record, "error_code", None),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(log_path: Path, level: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())
    if any(getattr(handler, "_chose_school_handler", False) for handler in root_logger.handlers):
        return

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler._chose_school_handler = True  # type: ignore[attr-defined]
    handler.setFormatter(JsonLineFormatter())
    root_logger.addHandler(handler)
