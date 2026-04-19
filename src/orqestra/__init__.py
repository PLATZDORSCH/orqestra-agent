"""Orqestra — multi-department agent orchestration."""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

from orqestra._paths import REPO_ROOT

try:
    __version__ = _pkg_version("orqestra")
except PackageNotFoundError:
    __version__ = "0.0.0+local"

__all__ = ["REPO_ROOT", "__version__"]
