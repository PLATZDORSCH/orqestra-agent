"""Background job events and department job state."""

from __future__ import annotations

import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass, field


@dataclass
class JobEvent:
    """A single progress event emitted by a running job."""
    type: str          # "tool_call" | "thinking"
    name: str          # tool name or thinking label
    preview: str       # short preview text
    detail: dict | None = None  # optional structured data (e.g. kb_write path)
    iteration: int = 0
    role: str | None = None  # e.g. RESEARCHER | CRITIC | VALIDATOR (proactive pipeline)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = {"type": self.type, "name": self.name, "preview": self.preview, "ts": self.timestamp}
        if self.detail:
            d["detail"] = self.detail
        if self.iteration:
            d["iteration"] = self.iteration
        if self.role:
            d["role"] = self.role
        return d

    @classmethod
    def from_dict(cls, d: dict) -> JobEvent:
        ts = float(d.get("ts", 0) or 0)
        if ts <= 0:
            ts = time.time()
        return cls(
            type=d.get("type", ""),
            name=d.get("name", ""),
            preview=d.get("preview", ""),
            detail=d.get("detail"),
            iteration=int(d.get("iteration", 0)),
            role=d.get("role"),
            timestamp=ts,
        )


@dataclass
class DepartmentJob:
    """A background department task tracked by the registry.

    A single job can be *replied to* multiple times — the conversation
    ``history`` grows and the job re-enters the running state each time.
    """

    id: str
    department: str
    task: str
    started_at: float = field(default_factory=time.time)
    history: list[dict] = field(default_factory=list)

    # Active execution state — None for historical jobs loaded from DB
    future: Future | None = None
    stop_event: threading.Event | None = None

    # Tool/thinking events (persisted in JobStore; cleared at each reply turn)
    events: list[JobEvent] = field(default_factory=list)

    # Deep-work loop: "single" = one shot; "deep" = work + self-eval until GOAL_REACHED or budget
    mode: str = "single"
    max_iterations: int = 1
    current_iteration: int = 0
    eval_status: str | None = None   # GOAL_REACHED | BUDGET_EXHAUSTED | CONTINUE | None
    progress_pct: int = 0

    # Optional: set when job is part of an orchestrator pipeline run
    pipeline_run_id: str | None = None

    # Proactive multi-phase: which mission template was used (if any)
    proactive_mission_id: str | None = None
    proactive_mission_label: str | None = None

    # Persisted fields (set when job finishes or loaded from DB)
    finished_at: float | None = None
    _stored_result: str | None = field(default=None, repr=False)
    _stored_error: str | None = field(default=None, repr=False)
    _stored_status: str | None = field(default=None, repr=False)

    def elapsed_seconds(self) -> float:
        end = self.finished_at if self.finished_at and not self._is_active() else time.time()
        return end - self.started_at

    def _is_active(self) -> bool:
        return self.future is not None and not self.future.done()

    def status(self) -> str:
        """pending | running | done | cancelled | error"""
        if self.future is None:
            st = self._stored_status or "done"
            # If the job has a finished_at timestamp it completed — trust the stored terminal
            # status (done / cancelled / error) instead of guessing from the in-flight state.
            if st in ("pending", "running"):
                if self.finished_at is not None:
                    # Finished cleanly but status was written mid-run; infer from stored data.
                    return "error" if self._stored_error else "done"
                # No finish timestamp → worker was killed mid-run (e.g. server restart).
                return "error"
            return st
        if self.future.cancelled():
            return "cancelled"
        if not self.future.done():
            return "running" if self.future.running() else "pending"
        exc = self.future.exception()
        if exc is not None:
            return "error"
        try:
            text = self.future.result()
        except Exception:
            return "error"
        if isinstance(text, str) and text.strip().startswith("[Job cancelled"):
            return "cancelled"
        return "done"

    def result_or_error(self) -> tuple[str | None, str | None]:
        """Return (result_text, error_message) when finished."""
        if self.future is None:
            return self._stored_result, self._stored_error
        if not self.future.done():
            return None, None
        exc = self.future.exception()
        if exc is not None:
            return None, f"{type(exc).__name__}: {exc}"
        try:
            return self.future.result(), None
        except Exception as e:
            return None, f"{type(e).__name__}: {e}"

    def chat_messages(self) -> list[dict]:
        """Full conversation transcript including all replies."""
        msgs: list[dict] = list(self.history)
        msgs.append({"role": "user", "content": self.task})
        result, err = self.result_or_error()
        if result is not None:
            msgs.append({"role": "assistant", "content": result})
        elif err is not None:
            msgs.append({"role": "assistant", "content": f"[Fehler: {err}]"})
        return msgs

    def to_record(self) -> dict:
        """Serialize to a dict suitable for JobStore.save()."""
        st = self.status()
        result, error = self.result_or_error()
        return {
            "id": self.id,
            "department": self.department,
            "task": self.task,
            "status": st,
            "result": result,
            "error": error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "history": self.history,
            "events": [e.to_dict() for e in self.events],
            "mode": self.mode,
            "max_iterations": self.max_iterations,
            "current_iteration": self.current_iteration,
            "eval_status": self.eval_status,
            "progress_pct": self.progress_pct,
            "pipeline_run_id": self.pipeline_run_id,
            "proactive_mission_id": self.proactive_mission_id,
            "proactive_mission_label": self.proactive_mission_label,
        }

    @staticmethod
    def _events_from_record(raw: list | None) -> list[JobEvent]:
        if not raw:
            return []
        out: list[JobEvent] = []
        for e in raw:
            if isinstance(e, dict):
                out.append(JobEvent.from_dict(e))
        return out

    @classmethod
    def from_record(cls, rec: dict) -> DepartmentJob:
        """Restore a historical job from a JobStore record (no future)."""
        return cls(
            id=rec["id"],
            department=rec["department"],
            task=rec["task"],
            started_at=rec["started_at"],
            history=rec.get("history", []),
            future=None,
            stop_event=None,
            events=cls._events_from_record(rec.get("events")),
            finished_at=rec.get("finished_at"),
            _stored_result=rec.get("result"),
            _stored_error=rec.get("error"),
            _stored_status=rec.get("status", "done"),
            mode=rec.get("mode") or "single",
            max_iterations=int(rec.get("max_iterations") or 1),
            current_iteration=int(rec.get("current_iteration") or 0),
            eval_status=rec.get("eval_status"),
            progress_pct=int(rec.get("progress_pct") or 0),
            pipeline_run_id=rec.get("pipeline_run_id"),
            proactive_mission_id=rec.get("proactive_mission_id"),
            proactive_mission_label=rec.get("proactive_mission_label"),
        )
