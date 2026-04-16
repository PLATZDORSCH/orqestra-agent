"""Shared pytest fixtures."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from orqestra.capabilities.knowledge import KnowledgeBase
from orqestra.core.job_store import JobStore


@pytest.fixture
def tmp_kb() -> KnowledgeBase:
    with tempfile.TemporaryDirectory() as d:
        kb = KnowledgeBase(Path(d))
        yield kb


@pytest.fixture
def tmp_job_store() -> JobStore:
    with tempfile.TemporaryDirectory() as d:
        store = JobStore(Path(d) / "jobs.sqlite")
        yield store
