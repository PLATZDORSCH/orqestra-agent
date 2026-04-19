"""SQLite-backed persistence for department jobs.

Stores completed (and in-progress) jobs so they survive server restarts
and can be continued with follow-up replies.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class JobStore:
    """Thread-safe SQLite store for job records."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._lock:
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id          TEXT PRIMARY KEY,
                    department  TEXT NOT NULL,
                    task        TEXT NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'pending',
                    result      TEXT,
                    error       TEXT,
                    started_at  REAL NOT NULL,
                    finished_at REAL,
                    history     TEXT NOT NULL DEFAULT '[]'
                );
            """)
            try:
                self._db.execute(
                    "ALTER TABLE jobs ADD COLUMN events TEXT NOT NULL DEFAULT '[]'",
                )
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise
            for col_sql in (
                "ALTER TABLE jobs ADD COLUMN mode TEXT NOT NULL DEFAULT 'single'",
                "ALTER TABLE jobs ADD COLUMN max_iterations INTEGER NOT NULL DEFAULT 1",
                "ALTER TABLE jobs ADD COLUMN current_iteration INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE jobs ADD COLUMN pipeline_run_id TEXT",
            ):
                try:
                    self._db.execute(col_sql)
                except sqlite3.OperationalError as e:
                    if "duplicate column" not in str(e).lower():
                        raise
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    id            TEXT PRIMARY KEY,
                    pipeline      TEXT NOT NULL,
                    status        TEXT NOT NULL,
                    variables     TEXT NOT NULL DEFAULT '{}',
                    steps         TEXT NOT NULL DEFAULT '[]',
                    current_step  INTEGER NOT NULL DEFAULT 0,
                    started_at    REAL NOT NULL,
                    finished_at   REAL,
                    error         TEXT
                );
            """)
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS proactive_state (
                    department           TEXT PRIMARY KEY,
                    last_mission_index   INTEGER NOT NULL DEFAULT 0
                );
            """)
            for col_sql in (
                "ALTER TABLE jobs ADD COLUMN proactive_mission_id TEXT",
                "ALTER TABLE jobs ADD COLUMN proactive_mission_label TEXT",
            ):
                try:
                    self._db.execute(col_sql)
                except sqlite3.OperationalError as e:
                    if "duplicate column" not in str(e).lower():
                        raise
            self._db.commit()

    def save(self, record: dict[str, Any]) -> None:
        """Insert or replace a job record."""
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO jobs "
                "(id, department, task, status, result, error, started_at, finished_at, history, events, "
                "mode, max_iterations, current_iteration, pipeline_run_id, proactive_mission_id, proactive_mission_label) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record["id"],
                    record["department"],
                    record["task"],
                    record["status"],
                    record.get("result"),
                    record.get("error"),
                    record["started_at"],
                    record.get("finished_at"),
                    json.dumps(record.get("history", []), ensure_ascii=False),
                    json.dumps(record.get("events", []), ensure_ascii=False),
                    record.get("mode", "single"),
                    int(record.get("max_iterations", 1)),
                    int(record.get("current_iteration", 0)),
                    record.get("pipeline_run_id"),
                    record.get("proactive_mission_id"),
                    record.get("proactive_mission_label"),
                ),
            )
            self._db.commit()

    def get(self, job_id: str) -> dict[str, Any] | None:
        """Fetch a single job by ID."""
        with self._lock:
            row = self._db.execute(
                "SELECT id, department, task, status, result, error, "
                "started_at, finished_at, history, events, mode, max_iterations, current_iteration, pipeline_run_id, "
                "proactive_mission_id, proactive_mission_label "
                "FROM jobs WHERE id=?",
                (job_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def list_all(self, *, limit: int = 200) -> list[dict[str, Any]]:
        """All jobs, newest first."""
        with self._lock:
            rows = self._db.execute(
                "SELECT id, department, task, status, result, error, "
                "started_at, finished_at, history, events, mode, max_iterations, current_iteration, pipeline_run_id, "
                "proactive_mission_id, proactive_mission_label "
                "FROM jobs "
                "ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def list_by_department(self, dept: str, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, department, task, status, result, error, "
                "started_at, finished_at, history, events, mode, max_iterations, current_iteration, pipeline_run_id, "
                "proactive_mission_id, proactive_mission_label "
                "FROM jobs "
                "WHERE department=? ORDER BY started_at DESC LIMIT ?",
                (dept, limit),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def list_done(self, *, department: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        """Jobs with status ``done``, newest first (for trajectory export)."""
        return self.list_for_export(status="done", department=department, limit=limit)

    def list_for_export(
        self,
        *,
        status: str = "done",
        department: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Filter jobs for trajectory export (default: completed jobs only)."""
        with self._lock:
            if department:
                rows = self._db.execute(
                    "SELECT id, department, task, status, result, error, "
                    "started_at, finished_at, history, events, mode, max_iterations, current_iteration, pipeline_run_id, "
                    "proactive_mission_id, proactive_mission_label "
                    "FROM jobs "
                    "WHERE status=? AND department=? "
                    "ORDER BY started_at DESC LIMIT ?",
                    (status, department, limit),
                ).fetchall()
            else:
                rows = self._db.execute(
                    "SELECT id, department, task, status, result, error, "
                    "started_at, finished_at, history, events, mode, max_iterations, current_iteration, pipeline_run_id, "
                    "proactive_mission_id, proactive_mission_label "
                    "FROM jobs "
                    "WHERE status=? ORDER BY started_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def delete(self, job_id: str) -> bool:
        with self._lock:
            cur = self._db.execute("DELETE FROM jobs WHERE id=?", (job_id,))
            self._db.commit()
            return cur.rowcount > 0

    @staticmethod
    def _row_to_dict(row: tuple) -> dict[str, Any]:
        ev_raw = row[9] if len(row) > 9 else None
        events: list[Any] = []
        if ev_raw:
            try:
                events = json.loads(ev_raw) if isinstance(ev_raw, str) else []
            except json.JSONDecodeError:
                events = []
        mode = row[10] if len(row) > 10 else "single"
        max_it = int(row[11]) if len(row) > 11 and row[11] is not None else 1
        cur_it = int(row[12]) if len(row) > 12 and row[12] is not None else 0
        pipeline_run_id = row[13] if len(row) > 13 else None
        proactive_mission_id = row[14] if len(row) > 14 else None
        proactive_mission_label = row[15] if len(row) > 15 else None
        return {
            "id": row[0],
            "department": row[1],
            "task": row[2],
            "status": row[3],
            "result": row[4],
            "error": row[5],
            "started_at": row[6],
            "finished_at": row[7],
            "history": json.loads(row[8]) if row[8] else [],
            "events": events,
            "mode": mode or "single",
            "max_iterations": max_it,
            "current_iteration": cur_it,
            "pipeline_run_id": pipeline_run_id,
            "proactive_mission_id": proactive_mission_id,
            "proactive_mission_label": proactive_mission_label,
        }

    def save_pipeline_run(self, record: dict[str, Any]) -> None:
        """Insert or replace a pipeline run record."""
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO pipeline_runs "
                "(id, pipeline, status, variables, steps, current_step, started_at, finished_at, error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record["id"],
                    record["pipeline"],
                    record["status"],
                    record.get("variables") or "{}",
                    record.get("steps") or "[]",
                    int(record.get("current_step", 0)),
                    record["started_at"],
                    record.get("finished_at"),
                    record.get("error"),
                ),
            )
            self._db.commit()

    def get_pipeline_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT id, pipeline, status, variables, steps, current_step, started_at, finished_at, error "
                "FROM pipeline_runs WHERE id=?",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "pipeline": row[1],
            "status": row[2],
            "variables": row[3],
            "steps": row[4],
            "current_step": row[5],
            "started_at": row[6],
            "finished_at": row[7],
            "error": row[8],
        }

    def list_pipeline_runs(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, pipeline, status, variables, steps, current_step, started_at, finished_at, error "
                "FROM pipeline_runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": r[0],
                "pipeline": r[1],
                "status": r[2],
                "variables": r[3],
                "steps": r[4],
                "current_step": r[5],
                "started_at": r[6],
                "finished_at": r[7],
                "error": r[8],
            }
            for r in rows
        ]

    def delete_pipeline_run(self, run_id: str) -> bool:
        with self._lock:
            cur = self._db.execute("DELETE FROM pipeline_runs WHERE id=?", (run_id,))
            self._db.commit()
            return cur.rowcount > 0

    def get_proactive_mission_index(self, department: str) -> int:
        """Last rotation index for proactive missions (strategy: rotate)."""
        with self._lock:
            row = self._db.execute(
                "SELECT last_mission_index FROM proactive_state WHERE department=?",
                (department,),
            ).fetchone()
        if not row:
            return 0
        return int(row[0] or 0)

    def set_proactive_mission_index(self, department: str, index: int) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO proactive_state (department, last_mission_index) VALUES (?, ?)",
                (department, int(index)),
            )
            self._db.commit()
