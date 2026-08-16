from __future__ import annotations

import json
from typing import Any, TextIO


def write_output(payload: Any, compact_json: bool, stream: TextIO) -> None:
    indent = None if compact_json else 2
    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
            sort_keys=compact_json,
            indent=indent,
        ),
        file=stream,
    )
