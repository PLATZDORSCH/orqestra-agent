"""Filesystem layout: repository root (config.yaml, templates/, web/, …).

``main.py`` and gateways live under ``src/orqestra/``; project data stays at the
repo root (parent of ``src/``).
"""

from __future__ import annotations

from pathlib import Path

# src/orqestra/_paths.py → package → src → repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
