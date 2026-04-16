"""JobStore SQLite persistence."""

from __future__ import annotations

import time

from orqestra.core.job_store import JobStore


def _minimal_record(job_id: str, dept: str = "d1", **extra):
    return {
        "id": job_id,
        "department": dept,
        "task": "task",
        "status": "done",
        "result": "ok",
        "error": None,
        "started_at": time.time(),
        "finished_at": time.time(),
        "history": [],
        "events": [],
        **extra,
    }


def test_save_get_roundtrip(tmp_job_store: JobStore):
    rec = _minimal_record("j1")
    tmp_job_store.save(rec)
    got = tmp_job_store.get("j1")
    assert got is not None
    assert got["id"] == "j1"
    assert got["task"] == "task"
    assert got["status"] == "done"


def test_list_all_ordering_newest_first(tmp_job_store: JobStore):
    t0 = time.time()
    tmp_job_store.save(_minimal_record("old", started_at=t0))
    tmp_job_store.save(_minimal_record("new", started_at=t0 + 10))
    rows = tmp_job_store.list_all(limit=10)
    ids = [r["id"] for r in rows]
    assert ids[0] == "new"


def test_delete(tmp_job_store: JobStore):
    tmp_job_store.save(_minimal_record("del", started_at=time.time()))
    assert tmp_job_store.delete("del")
    assert tmp_job_store.get("del") is None


def test_schema_migration_duplicate_column_guard(tmp_job_store: JobStore):
    """Re-opening store should not fail on duplicate ALTER columns."""
    path = tmp_job_store._db_path
    store2 = JobStore(path)
    store2.save(_minimal_record("x", started_at=time.time()))
    assert store2.get("x") is not None
