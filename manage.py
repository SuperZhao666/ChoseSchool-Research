"""Repository-local command entry point.

This wrapper keeps commands usable before the package is installed.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from chose_school.main import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
