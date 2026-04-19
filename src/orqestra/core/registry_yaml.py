"""Load/save departments.yaml."""

from __future__ import annotations

import logging
from pathlib import Path
import yaml

log = logging.getLogger(__name__)


def _check_path_is_file_or_missing(path: Path) -> None:
    """Guard against the classic Docker bind-mount foot-gun.

    If the bind-mount source on the host doesn't exist, Docker silently
    creates a directory in its place — both on the host and inside the
    container. We then crash later with IsADirectoryError. Catch it
    early with an actionable hint instead.
    """
    if path.is_dir():
        raise RuntimeError(
            f"{path} exists as a directory but must be a regular file. "
            "This usually means Docker auto-created the bind-mount target "
            "because the host file was missing. "
            f"Fix on the host: `rmdir {path.name} && touch {path.name}` "
            "(or run scripts/bootstrap.sh once before `docker compose up`).",
        )


def load_departments_yaml(root: Path) -> list[dict]:
    """Load department definitions from departments.yaml (or empty list if missing)."""
    path = root / "departments.yaml"
    _check_path_is_file_or_missing(path)
    if not path.is_file():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        log.exception("Failed to read departments.yaml")
        return []
    return list(data.get("departments") or [])


def save_departments_yaml(root: Path, departments: list[dict]) -> None:
    """Persist department definitions to departments.yaml."""
    path = root / "departments.yaml"
    _check_path_is_file_or_missing(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "# Departments — created via Web UI (Department Builder) or edited manually.\n"
            "# Restart the API after manual edits, or use the API to apply changes at runtime.\n",
        )
        yaml.dump(
            {"departments": departments},
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )


__all__ = ["load_departments_yaml", "save_departments_yaml"]
