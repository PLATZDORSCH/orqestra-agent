"""DepartmentRegistry core: departments map, install, search."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from orqestra.capabilities.knowledge import KnowledgeBase, create_kb_capabilities
from orqestra.capabilities.skills import create_skill_capabilities
from orqestra.core.capabilities import CapabilityManager
from orqestra.core.department import DEPARTMENT_CAPABILITIES, Department, SHARED_CAPS
from orqestra.core.engine import StrategyEngine
from orqestra.core.job_store import JobStore
from orqestra.core.jobs import DepartmentJob
from orqestra.core.proactive import _PROACTIVE_ROLES
from orqestra.core.proactive_models import parse_proactive_from_dict
from orqestra.core.registry_constants import DEFAULT_DEPT_COLORS

log = logging.getLogger(__name__)


class DepartmentRegistryCore:
    """Builds and holds all departments (base state + install helpers)."""

    def __init__(self, *, max_workers: int = 5, max_queued: int = 20) -> None:
        self._departments: dict[str, Department] = {}
        self._max_workers = max_workers
        self._max_queued = max_queued
        self._executor: ThreadPoolExecutor | None = None
        self._jobs: dict[str, DepartmentJob] = {}
        self._job_counter = 0
        self._lock = threading.Lock()
        self._job_store: JobStore | None = None
        self._proactive_iterations: int = len(_PROACTIVE_ROLES)

    def set_proactive_iterations(self, n: int) -> None:
        """How many pipeline phases to run (capped by available role definitions)."""
        self._proactive_iterations = max(1, min(int(n), len(_PROACTIVE_ROLES)))

    @property
    def job_store(self) -> JobStore | None:
        return self._job_store

    def _active_job_count(self) -> int:
        return sum(
            1 for j in self._jobs.values()
            if j.status() in ("pending", "running")
        )

    def _check_queue_capacity(self) -> None:
        if self._active_job_count() >= self._max_workers + self._max_queued:
            raise RuntimeError("Job-Queue voll — bitte warten")

    def _ensure_executor(self) -> None:
        """Create the thread pool if missing (e.g. no departments yet, or after last dept removed)."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)

    def set_job_store(self, store: JobStore) -> None:
        """Attach a persistent job store and load historical jobs."""
        self._job_store = store
        records = store.list_all(limit=500)
        repaired = 0
        with self._lock:
            for rec in records:
                if rec["id"] not in self._jobs:
                    # Repair stale "running"/"pending" status from previous server session
                    if rec.get("status") in ("running", "pending") and rec.get("finished_at"):
                        rec["status"] = "error" if rec.get("error") else "done"
                        repaired += 1
                        try:
                            store.save(rec)
                        except Exception:
                            pass
                    self._jobs[rec["id"]] = DepartmentJob.from_record(rec)
                    counter_part = rec["id"].rsplit("-", 1)
                    if len(counter_part) == 2 and counter_part[1].isdigit():
                        self._job_counter = max(self._job_counter, int(counter_part[1]))
        if records:
            log.info("Loaded %d historical jobs from DB (%d repaired)", len(records), repaired)

    def build(
        self,
        departments_cfg: list[dict],
        root: Path,
        llm_base_url: str,
        llm_api_key: str,
        llm_model: str,
        language: str | None = None,
        context_window: int = 0,
        summarize_at: float = 0.7,
        project_context: str | None = None,
    ) -> None:
        self._project_context = project_context
        for dept_index, dept_cfg in enumerate(departments_cfg):
            name = dept_cfg["name"]
            dept = self._install_department(
                dept_cfg,
                root=root,
                llm_base_url=llm_base_url,
                llm_api_key=llm_api_key,
                llm_model=llm_model,
                language=language,
                context_window=context_window,
                summarize_at=summarize_at,
                project_context=project_context,
                dept_index=dept_index,
            )
            self._departments[name] = dept

        if self._departments and self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)

    def _install_department(
        self,
        dept_cfg: dict,
        *,
        root: Path,
        llm_base_url: str,
        llm_api_key: str,
        llm_model: str,
        language: str | None = None,
        context_window: int = 0,
        summarize_at: float = 0.7,
        project_context: str | None = None,
        dept_index: int = 0,
    ) -> Department:
        name = dept_cfg["name"]
        label = dept_cfg.get("label", name.title())
        raw_color = dept_cfg.get("color")
        if isinstance(raw_color, str) and raw_color.strip():
            dept_color = raw_color.strip()
        else:
            dept_color = DEFAULT_DEPT_COLORS[dept_index % len(DEFAULT_DEPT_COLORS)]
        raw_icon = dept_cfg.get("icon")
        if isinstance(raw_icon, str) and raw_icon.strip():
            dept_icon = raw_icon.strip()
        else:
            dept_icon = None
        proactive_cfg = parse_proactive_from_dict(dept_cfg.get("proactive"))
        persona_path = root / dept_cfg.get("persona", f"departments/{name}/persona.md")
        kb_path = root / dept_cfg.get("knowledge_base", f"departments/{name}/knowledge_base")
        skills_path = root / dept_cfg.get("skills", f"departments/{name}/skills")

        global_skills = root / "skills"
        kb = KnowledgeBase(kb_path)
        skills_path.mkdir(parents=True, exist_ok=True)

        mgr = CapabilityManager()
        for cap in create_kb_capabilities(kb):
            mgr.add(cap)
        for cap in create_skill_capabilities(
            skills_path, global_skills_dir=global_skills, language=language,
        ):
            mgr.add(cap)

        cap_names = dept_cfg.get("capabilities", DEPARTMENT_CAPABILITIES.get(name, []))
        for cap_name in cap_names:
            if cap_name in SHARED_CAPS:
                mgr.add(SHARED_CAPS[cap_name])

        model = dept_cfg.get("model", llm_model)

        memory_prompt = self._load_dept_memory(kb_path)

        engine = StrategyEngine(
            base_url=llm_base_url,
            api_key=llm_api_key,
            model=model,
            capabilities=mgr,
            persona_path=persona_path,
            memory_prompt=memory_prompt,
            project_context=project_context,
            max_rounds=dept_cfg.get("max_rounds", 90),
            language=language,
            context_window=int(dept_cfg.get("context_window", context_window)),
            summarize_at=float(dept_cfg.get("summarize_at", summarize_at)),
            on_thinking=None,
            on_tool_call=None,
            on_tool_done=None,
        )

        dept = Department(
            name,
            label,
            engine,
            kb,
            skills_path,
            color=dept_color,
            icon=dept_icon,
            proactive=proactive_cfg,
        )
        log.info(
            "Department '%s' loaded — %d capabilities, %d skills",
            name, len(mgr), len(dept.skills_summary()),
        )
        return dept

    def add_department(
        self,
        dept_cfg: dict,
        *,
        root: Path,
        llm_base_url: str,
        llm_api_key: str,
        llm_model: str,
        language: str | None = None,
        context_window: int = 0,
        summarize_at: float = 0.7,
        project_context: str | None = None,
    ) -> Department:
        """Register a single department at runtime (must not already exist)."""
        name = dept_cfg["name"]
        if name in self._departments:
            raise ValueError(f"Department already exists: {name}")
        dept = self._install_department(
            dept_cfg,
            root=root,
            llm_base_url=llm_base_url,
            llm_api_key=llm_api_key,
            llm_model=llm_model,
            language=language,
            context_window=context_window,
            summarize_at=summarize_at,
            project_context=project_context or getattr(self, "_project_context", None),
            dept_index=len(self._departments),
        )
        self._departments[name] = dept
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        return dept

    def remove_department(self, name: str) -> bool:
        """Remove a department from the registry. Shuts down executor if none remain."""
        if name not in self._departments:
            return False
        del self._departments[name]
        if not self._departments and self._executor is not None:
            self._executor.shutdown(wait=True, cancel_futures=False)
            self._executor = None
            log.info("Department executor shut down (no departments left)")
        return True

    @staticmethod
    def _load_dept_memory(kb_path: Path) -> str | None:
        mem_file = kb_path / "wiki" / "memory.md"
        if not mem_file.is_file():
            return None
        try:
            import frontmatter as fm
            doc = fm.load(str(mem_file))
            body = (doc.content or "").strip()
            return body[:4000] if body else None
        except Exception:
            return None

    def get(self, name: str) -> Department | None:
        return self._departments.get(name)

    def names(self) -> list[str]:
        return list(self._departments)

    def items(self) -> list[tuple[str, Department]]:
        return list(self._departments.items())

    def search_all(self, query: str, limit: int = 5) -> list[dict]:
        results = []
        for name, dept in self._departments.items():
            for hit in dept.search(query, limit=limit):
                hit["department"] = name
                results.append(hit)
        return results

    def __len__(self) -> int:
        return len(self._departments)
