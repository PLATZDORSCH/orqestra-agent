"""Paths and logging config shared by the API package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from orqestra._paths import REPO_ROOT as ROOT

# Used when the API runs embedded in the CLI (quiet=True): no uvicorn/FastAPI/gateway lines on stderr.
QUIET_UVICORN_LOG_CONFIG: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "quiet": {
            "class": "logging.NullHandler",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["quiet"], "level": "CRITICAL", "propagate": False},
        "uvicorn.error": {"handlers": ["quiet"], "level": "CRITICAL", "propagate": False},
        "uvicorn.access": {"handlers": ["quiet"], "level": "CRITICAL", "propagate": False},
        "uvicorn.asgi": {"handlers": ["quiet"], "level": "CRITICAL", "propagate": False},
        "fastapi": {"handlers": ["quiet"], "level": "CRITICAL", "propagate": False},
        "starlette": {"handlers": ["quiet"], "level": "CRITICAL", "propagate": False},
        "gateway_api": {"handlers": ["quiet"], "level": "CRITICAL", "propagate": False},
    },
}
