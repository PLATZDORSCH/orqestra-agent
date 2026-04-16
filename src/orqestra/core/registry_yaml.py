"""Load/save departments.yaml."""

from __future__ import annotations

import logging
from pathlib import Path
import yaml

log = logging.getLogger(__name__)


def load_departments_yaml(root: Path) -> list[dict]:
    """Load department definitions from departments.yaml (or empty list if missing)."""
    path = root / "departments.yaml"
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
