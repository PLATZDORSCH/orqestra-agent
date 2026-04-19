#!/usr/bin/env python3
"""Compatibility shim — real implementation: ``src/orqestra/main.py``.

Nach dem src-Layout liegt der Code unter ``src/orqestra/``. Du kannst:

- ``python main.py`` (dieses Skript; legt ``src/`` auf ``sys.path``, falls nötig)
- ``pip install -e .`` und dann ``orqestra`` oder ``python -m orqestra.main``
"""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
_src = _root / "src"
if _src.is_dir():
    p = str(_src)
    if p not in sys.path:
        sys.path.insert(0, p)

from orqestra.main import main

if __name__ == "__main__":
    main()
