from __future__ import annotations

import logging
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

from chose_school.access.cli_parser import parse_arguments
from chose_school.access.command_handlers import dispatch_command
from chose_school.access.output import write_output
from chose_school.bootstrap import build_application
from chose_school.domain.errors import ChoseSchoolError
from chose_school.domain.models import Settings
from chose_school.infrastructure.config import load_settings
from chose_school.infrastructure.observability import configure_logging


LOGGER = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    trace_id = str(uuid.uuid4())
    started_at = time.perf_counter()
    settings: Settings | None = None
    try:
        settings = _load_runtime_settings(arguments.config, arguments.database)
        configure_logging(settings.log_path, settings.log_level)
        _log_command_started(arguments.command, trace_id, settings.profile_key)
        application = build_application(settings)
        if arguments.command not in {"init", "backup"}:
            application.database.require_current_schema()
        result = dispatch_command(arguments, application, trace_id)
        _log_command_completed(
            arguments.command,
            trace_id,
            settings.profile_key,
            started_at,
            result,
        )
        write_output(result, arguments.json, sys.stdout)
        return 0
    except ChoseSchoolError as error:
        _report_expected_error(error, arguments.command, trace_id, settings, started_at)
        return 1
    except (FileNotFoundError, FileExistsError, OSError) as error:
        wrapped_error = ChoseSchoolError("IO_ERROR", str(error))
        _report_expected_error(wrapped_error, arguments.command, trace_id, settings, started_at)
        return 1
    except Exception as error:
        _report_system_error(error, arguments.command, trace_id, settings, started_at)
        return 1


def _load_runtime_settings(
    config_path: str | None,
    database_path: str | None,
) -> Settings:
    settings = load_settings(config_path=Path(config_path) if config_path else None)
    if database_path is None:
        return settings
    override_path = Path(database_path)
    if not override_path.is_absolute():
        override_path = settings.repository_root / override_path
    return replace(settings, database_path=override_path)


def _log_command_started(command: str, trace_id: str, profile_key: str) -> None:
    LOGGER.info(
        "command started",
        extra=_log_context(command, trace_id, profile_key, "running"),
    )


def _log_command_completed(
    command: str,
    trace_id: str,
    profile_key: str,
    started_at: float,
    result: Any,
) -> None:
    context = _log_context(command, trace_id, profile_key, "succeeded")
    context["duration_ms"] = _duration_ms(started_at)
    context["result_count"] = _result_count(result)
    LOGGER.info("command completed", extra=context)


def _report_expected_error(
    error: ChoseSchoolError,
    command: str,
    trace_id: str,
    settings: Settings | None,
    started_at: float,
) -> None:
    context = _log_context(command, trace_id, _profile_key(settings), "rejected")
    context.update(
        {
            "duration_ms": _duration_ms(started_at),
            "error_code": error.error_code,
        }
    )
    LOGGER.warning(error.message, extra=context)
    write_output(
        {
            "error_code": error.error_code,
            "message": error.message,
            "trace_id": trace_id,
        },
        True,
        sys.stderr,
    )


def _report_system_error(
    error: Exception,
    command: str,
    trace_id: str,
    settings: Settings | None,
    started_at: float,
) -> None:
    context = _log_context(command, trace_id, _profile_key(settings), "failed")
    context.update(
        {
            "duration_ms": _duration_ms(started_at),
            "error_code": "SYSTEM_ERROR",
        }
    )
    LOGGER.exception("unexpected command failure", extra=context)
    write_output(
        {
            "error_code": "SYSTEM_ERROR",
            "message": "系统错误，请使用TraceId查询本地日志",
            "trace_id": trace_id,
        },
        True,
        sys.stderr,
    )


def _log_context(
    command: str,
    trace_id: str,
    profile_key: str,
    status: str,
) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "user_id": profile_key,
        "operation": command,
        "status": status,
    }


def _profile_key(settings: Settings | None) -> str:
    return settings.profile_key if settings else "unknown"


def _duration_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


def _result_count(result: Any) -> int | None:
    if isinstance(result, (list, tuple)):
        return len(result)
    if isinstance(result, dict) and isinstance(result.get("rows"), int):
        return int(result["rows"])
    return None
