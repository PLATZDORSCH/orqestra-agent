"""Version endpoint — exposes the running package version."""

from __future__ import annotations

import platform
import sys

from fastapi import APIRouter

from orqestra import __version__

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/version")
def get_version() -> dict[str, str]:
    """Return the running Orqestra version + minimal runtime info."""
    return {
        "version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(terse=True),
    }
