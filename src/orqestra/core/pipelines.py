"""Orchestrator pipelines: sequential department jobs with template variables."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from orqestra._paths import REPO_ROOT
from orqestra.core.capabilities import Capability
from orqestra.core.job_store import JobStore
from orqestra.core.localization import normalize_language, resolve_task_template_localized

log = logging.getLogger(__name__)

ORCHESTRATOR_PIPELINE_TOOL_NAMES = ("run_pipeline", "check_pipeline")

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def extract_placeholders(template: str) -> list[str]:
    """Return unique placeholder names in order of first appearance."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _PLACEHOLDER_RE.finditer(template):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def render_task_template(template: str, variables: dict[str, str]) -> str:
    """Replace {key} with variables[key]; missing keys become empty string."""

    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        return str(variables.get(key, ""))

    return _PLACEHOLDER_RE.sub(repl, template)


@dataclass
class PipelineStep:
    department: str
    task_template: str
    result_key: str | None = None
    mode: str = "deep"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "department": self.department,
            "task_template": self.task_template,
            "mode": self.mode,
        }
        if self.result_key:
            d["result_key"] = self.result_key
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any], *, language: str | None = None) -> PipelineStep:
        raw = d.get("task_template", "")
        tt = resolve_task_template_localized(raw, language) if isinstance(raw, (str, dict)) else str(raw)
        return cls(
            department=str(d["department"]),
            task_template=tt,
            result_key=d.get("result_key") or None,
            mode=str(d.get("mode") or "deep"),
        )


@dataclass
class PipelineDef:
    name: str
    label: str
    description: str = ""
    steps: list[PipelineStep] = field(default_factory=list)
    variable_descriptions: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
        }
        if self.variable_descriptions:
            d["variable_descriptions"] = self.variable_descriptions
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any], *, language: str | None = None) -> PipelineDef:
        steps_raw = d.get("steps") or []
        steps: list[PipelineStep] = []
        for s in steps_raw:
            if isinstance(s, dict):
                steps.append(PipelineStep.from_dict(s, language=language))
        var_desc = d.get("variable_descriptions") or {}
        lang = normalize_language(language)
        label = str(d.get("label") or d["name"])
        desc = str(d.get("description") or "")
        if lang == "de":
            if d.get("label_de"):
                label = str(d["label_de"])
            if d.get("description_de"):
                desc = str(d["description_de"])
        return cls(
            name=str(d["name"]),
            label=label,
            description=desc,
            steps=[s for s in steps if s.department and s.task_template],
            variable_descriptions={str(k): str(v) for k, v in var_desc.items()} if isinstance(var_desc, dict) else {},
        )


@dataclass
class PipelineRunStepState:
    department: str
    job_id: str | None = None
    status: str = "pending"
    result_key: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "department": self.department,
            "status": self.status,
        }
        if self.job_id:
            d["job_id"] = self.job_id
        if self.result_key:
            d["result_key"] = self.result_key
        if self.error:
            d["error"] = self.error
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PipelineRunStepState:
        return cls(
            department=str(d.get("department", "")),
            job_id=d.get("job_id"),
            status=str(d.get("status") or "pending"),
            result_key=d.get("result_key"),
            error=d.get("error"),
        )


@dataclass
class PipelineRun:
    id: str
    pipeline: str
    status: str  # pending | running | done | error | cancelled
    variables: dict[str, str]
    step_states: list[PipelineRunStepState]
    current_step: int = 0
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    error: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pipeline": self.pipeline,
            "status": self.status,
            "variables": json.dumps(self.variables, ensure_ascii=False),
            "steps": json.dumps([s.to_dict() for s in self.step_states], ensure_ascii=False),
            "current_step": self.current_step,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }

    @classmethod
    def from_record(cls, rec: dict[str, Any]) -> PipelineRun:
        vars_raw = rec.get("variables") or "{}"
        try:
            variables = json.loads(vars_raw) if isinstance(vars_raw, str) else dict(vars_raw or {})
        except json.JSONDecodeError:
            variables = {}
        steps_raw = rec.get("steps") or "[]"
        try:
            arr = json.loads(steps_raw) if isinstance(steps_raw, str) else steps_raw
        except json.JSONDecodeError:
            arr = []
        step_states = [PipelineRunStepState.from_dict(x) for x in arr if isinstance(x, dict)]
        return cls(
            id=rec["id"],
            pipeline=rec["pipeline"],
            status=rec.get("status") or "pending",
            variables={k: str(v) for k, v in variables.items()},
            step_states=step_states,
            current_step=int(rec.get("current_step") or 0),
            started_at=float(rec.get("started_at") or time.time()),
            finished_at=rec.get("finished_at"),
            error=rec.get("error"),
        )


def load_pipelines_yaml(root: Path, language: str | None = None) -> list[PipelineDef]:
    path = root / "pipelines.yaml"
    if not path.is_file():
        return []
    if language is None:
        try:
            cfg_path = root / "config.yaml"
            if cfg_path.is_file():
                with open(cfg_path, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                language = (cfg.get("engine") or {}).get("language")
        except Exception:
            language = None
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        log.exception("Failed to read pipelines.yaml")
        return []
    raw_list = data.get("pipelines") or []
    out: list[PipelineDef] = []
    for item in raw_list:
        if isinstance(item, dict):
            try:
                out.append(PipelineDef.from_dict(item, language=language))
            except (KeyError, TypeError):
                log.warning("Skipping invalid pipeline entry: %s", item)
    return out


def save_pipelines_yaml(root: Path, pipelines: list[PipelineDef]) -> None:
    path = root / "pipelines.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "# Orchestrator pipelines — sequential department chains.\n"
            "# Editable here or via the web UI (Pipelines).\n\n",
        )
        yaml.dump(
            {"pipelines": [p.to_dict() for p in pipelines]},
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )


class PipelineRunner:
    """Loads pipeline definitions, runs them sequentially via DepartmentRegistry."""

    def __init__(
        self,
        root: Path,
        registry: Any,
        job_store: JobStore | None = None,
    ) -> None:
        self._root = root
        self._registry = registry
        self._job_store = job_store
        self._lock = threading.Lock()
        self._pipelines: dict[str, PipelineDef] = {}
        self._runs: dict[str, PipelineRun] = {}
        self._run_counter = 0
        self._cancel_events: dict[str, threading.Event] = {}
        self.reload()
        if self._job_store is not None:
            self._load_runs_from_store()

    def reload(self) -> None:
        with self._lock:
            defs = load_pipelines_yaml(self._root)
            self._pipelines = {p.name: p for p in defs}

    @property
    def pipelines(self) -> list[PipelineDef]:
        with self._lock:
            return list(self._pipelines.values())

    def get_pipeline(self, name: str) -> PipelineDef | None:
        with self._lock:
            return self._pipelines.get(name)

    def set_pipelines(self, pipelines: list[PipelineDef]) -> None:
        with self._lock:
            self._pipelines = {p.name: p for p in pipelines}
        save_pipelines_yaml(self._root, pipelines)

    def delete_pipeline(self, name: str) -> bool:
        with self._lock:
            if name not in self._pipelines:
                return False
            del self._pipelines[name]
            save_pipelines_yaml(self._root, list(self._pipelines.values()))
        return True

    def upsert_pipeline(self, p: PipelineDef) -> None:
        with self._lock:
            self._pipelines[p.name] = p
            save_pipelines_yaml(self._root, list(self._pipelines.values()))

    def _persist_run(self, run: PipelineRun) -> None:
        if self._job_store is None:
            return
        try:
            self._job_store.save_pipeline_run(run.to_record())
        except Exception:
            log.debug("Failed to persist pipeline run %s", run.id, exc_info=True)

    def _load_runs_from_store(self) -> None:
        if self._job_store is None:
            return
        try:
            records = self._job_store.list_pipeline_runs(limit=500)
        except Exception:
            return
        for rec in records:
            try:
                run = PipelineRun.from_record(rec)
                self._runs[run.id] = run
                part = run.id.rsplit("-", 1)
                if len(part) == 2 and part[1].isdigit():
                    self._run_counter = max(self._run_counter, int(part[1]))
            except Exception:
                pass

    def attach_job_store(self, job_store: JobStore) -> None:
        self._job_store = job_store
        self._load_runs_from_store()

    def get_run(self, run_id: str) -> PipelineRun | None:
        with self._lock:
            r = self._runs.get(run_id)
            if r:
                return r
        if self._job_store:
            rec = self._job_store.get_pipeline_run(run_id)
            if rec:
                return PipelineRun.from_record(rec)
        return None

    def list_runs(self, limit: int = 100) -> list[PipelineRun]:
        with self._lock:
            runs = list(self._runs.values())
        runs.sort(key=lambda x: x.started_at, reverse=True)
        return runs[:limit]

    def start_run(
        self,
        pipeline_name: str,
        variables: dict[str, str],
        *,
        mode_override: str | None = None,
    ) -> PipelineRun:
        pdef = self.get_pipeline(pipeline_name)
        if pdef is None:
            raise ValueError(f"Unknown pipeline: {pipeline_name}")
        if not pdef.steps:
            raise ValueError(f"Pipeline has no steps: {pipeline_name}")

        # User must supply placeholders not produced by earlier steps' result_key
        produced: set[str] = set(variables.keys())
        missing: list[str] = []
        for step in pdef.steps:
            for ph in extract_placeholders(step.task_template):
                if ph in produced:
                    continue
                missing.append(ph)
            if step.result_key:
                produced.add(step.result_key)
        if missing:
            raise ValueError(
                f"Missing variables for placeholders: {', '.join(sorted(set(missing)))}",
            )

        with self._lock:
            self._run_counter += 1
            run_id = f"{pipeline_name}-run-{self._run_counter}"

        step_states = [
            PipelineRunStepState(department=s.department, result_key=s.result_key)
            for s in pdef.steps
        ]
        run = PipelineRun(
            id=run_id,
            pipeline=pipeline_name,
            status="running",
            variables=dict(variables),
            step_states=step_states,
            current_step=0,
        )
        cancel_ev = threading.Event()
        with self._lock:
            self._runs[run.id] = run
            self._cancel_events[run.id] = cancel_ev
        self._persist_run(run)

        def worker() -> None:
            try:
                self._execute_run(pdef, run, cancel_ev, mode_override)
            except Exception as exc:
                log.exception("Pipeline run failed")
                run.status = "error"
                run.error = f"{type(exc).__name__}: {exc}"
                run.finished_at = time.time()
                self._persist_run(run)
            finally:
                with self._lock:
                    self._cancel_events.pop(run.id, None)

        t = threading.Thread(target=worker, name=f"pipeline-{run_id}", daemon=True)
        t.start()
        return run

    def _execute_run(
        self,
        pdef: PipelineDef,
        run: PipelineRun,
        cancel_ev: threading.Event,
        mode_override: str | None,
    ) -> None:
        vars_map: dict[str, str] = dict(run.variables)

        for i, step in enumerate(pdef.steps):
            if cancel_ev.is_set():
                run.status = "cancelled"
                run.finished_at = time.time()
                run.current_step = i
                self._persist_run(run)
                return

            run.current_step = i
            task_text = render_task_template(step.task_template, vars_map)
            mode = mode_override or step.mode
            if mode not in ("single", "deep", "proactive"):
                mode = "deep"

            st = run.step_states[i]
            st.status = "running"

            job = self._registry.submit_job(
                step.department,
                task_text,
                mode=mode,
                pipeline_run_id=run.id,
            )
            st.job_id = job.id
            self._persist_run(run)

            # Poll until terminal
            while True:
                if cancel_ev.is_set():
                    if job.stop_event:
                        job.stop_event.set()
                    st.status = "cancelled"
                    run.status = "cancelled"
                    run.finished_at = time.time()
                    self._persist_run(run)
                    return

                j = self._registry.get_job(job.id)
                if j is None:
                    st.status = "error"
                    st.error = "Job disappeared"
                    run.status = "error"
                    run.error = st.error
                    run.finished_at = time.time()
                    self._persist_run(run)
                    return

                status = j.status()
                if status in ("pending", "running"):
                    time.sleep(0.4)
                    continue

                if status == "cancelled":
                    st.status = "cancelled"
                    run.status = "cancelled"
                    run.finished_at = time.time()
                    self._persist_run(run)
                    return

                if status == "error":
                    result, err = j.result_or_error()
                    st.status = "error"
                    st.error = err or result or "Unknown error"
                    run.status = "error"
                    run.error = st.error
                    run.finished_at = time.time()
                    self._persist_run(run)
                    return

                # done
                result, _ = j.result_or_error()
                text = (result or "").strip()
                st.status = "done"
                if step.result_key:
                    vars_map[step.result_key] = text
                    run.variables[step.result_key] = text
                self._persist_run(run)
                break

        run.status = "done"
        run.finished_at = time.time()
        run.current_step = len(pdef.steps)
        self._persist_run(run)

    def create_run_pipeline_capability(self) -> Capability:
        runner = self

        def handle_run(args: dict[str, Any]) -> str:
            name = str(args.get("pipeline_name") or "").strip()
            raw_vars = args.get("variables")
            if not isinstance(raw_vars, dict):
                raw_vars = {}
            str_vars = {str(k): str(v) for k, v in raw_vars.items()}
            if not name:
                return json.dumps({"error": "pipeline_name is required"}, ensure_ascii=False)
            try:
                run = runner.start_run(name, str_vars)
                return json.dumps(
                    {
                        "run_id": run.id,
                        "pipeline": run.pipeline,
                        "status": run.status,
                        "message": (
                            "Pipeline run started. Use **check_pipeline** with run_id for progress "
                            "until status is done, error, or cancelled."
                        ),
                    },
                    ensure_ascii=False,
                )
            except Exception as exc:
                log.exception("run_pipeline failed")
                return json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False)

        return Capability(
            name="run_pipeline",
            description=(
                "Start a **named orchestrator pipeline** (sequential department jobs defined in "
                "`pipelines.yaml`). Pass **pipeline_name** and **variables** (object) for placeholders "
                "in the first step templates. Returns **run_id** immediately — use **check_pipeline** to poll. "
                f"Available pipelines: {', '.join(p.name for p in self.pipelines) or '(none)'}"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "pipeline_name": {
                        "type": "string",
                        "description": "Pipeline id (name field from pipelines.yaml)",
                    },
                    "variables": {
                        "type": "object",
                        "description": "String key/value map for {placeholder} in task templates",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["pipeline_name"],
            },
            handler=handle_run,
        )

    def create_check_pipeline_capability(self) -> Capability:
        runner = self

        def handle_check(args: dict[str, Any]) -> str:
            run_id = str(args.get("run_id") or "").strip()
            if not run_id:
                return json.dumps({"error": "run_id is required"}, ensure_ascii=False)
            run = runner.get_run(run_id)
            if run is None:
                return json.dumps({"error": f"Unknown pipeline run: {run_id}"}, ensure_ascii=False)
            out: dict[str, Any] = {
                "run_id": run.id,
                "pipeline": run.pipeline,
                "status": run.status,
                "current_step": run.current_step,
                "total_steps": len(run.step_states),
                "elapsed_seconds": round(time.time() - run.started_at, 1),
            }
            if run.error:
                out["error"] = run.error
            if run.finished_at:
                out["finished_at"] = run.finished_at
            out["steps"] = [s.to_dict() for s in run.step_states]
            return json.dumps(out, ensure_ascii=False)

        return Capability(
            name="check_pipeline",
            description=(
                "Check status of a **pipeline run** started with **run_pipeline**. "
                "Pass **run_id**. When status is done, error, or cancelled, the run is finished."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "description": "run_id from run_pipeline"},
                },
                "required": ["run_id"],
            },
            handler=handle_check,
        )

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            ev = self._cancel_events.get(run_id)
            run = self._runs.get(run_id)
        if ev is None:
            run = self.get_run(run_id)
            if run and run.status in ("done", "error", "cancelled"):
                return {"error": f"Run {run_id} is already finished"}
            return {"error": f"Unknown or inactive pipeline run: {run_id}"}
        ev.set()
        return {"success": True, "run_id": run_id}

    def delete_run(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            existed_mem = run_id in self._runs
            self._runs.pop(run_id, None)
            self._cancel_events.pop(run_id, None)
        ok_db = False
        if self._job_store:
            ok_db = self._job_store.delete_pipeline_run(run_id)
        if existed_mem or ok_db:
            return {"success": True, "run_id": run_id}
        return {"error": f"Unknown run: {run_id}"}


# ── Pipeline templates ────────────────────────────────────────────────

_PIPELINE_TEMPLATES_DIR = REPO_ROOT / "templates" / "pipelines"


def list_pipeline_templates() -> list[dict[str, Any]]:
    """Return available pipeline templates from templates/pipelines/."""
    if not _PIPELINE_TEMPLATES_DIR.is_dir():
        return []
    results: list[dict[str, Any]] = []
    for yf in sorted(_PIPELINE_TEMPLATES_DIR.glob("*.yaml")):
        try:
            with open(yf, encoding="utf-8") as f:
                tpl = yaml.safe_load(f) or {}
        except Exception:
            log.warning("Skipping invalid pipeline template: %s", yf)
            continue
        results.append({
            "name": tpl.get("name", yf.stem),
            "label": tpl.get("label", yf.stem.replace("-", " ").title()),
            "label_de": tpl.get("label_de", ""),
            "description": tpl.get("description", ""),
            "description_de": tpl.get("description_de", ""),
            "required_departments": tpl.get("required_departments", []),
            "steps_count": len(tpl.get("steps", [])),
        })
    return results


def install_pipeline_template(
    template_name: str,
    runner: PipelineRunner,
    *,
    language: str | None = None,
) -> PipelineDef:
    """Install a pipeline template into pipelines.yaml via the runner."""
    yf = _PIPELINE_TEMPLATES_DIR / f"{template_name}.yaml"
    if not yf.is_file():
        raise ValueError(f"Pipeline template not found: {template_name}")
    with open(yf, encoding="utf-8") as f:
        tpl = yaml.safe_load(f) or {}

    if runner.get_pipeline(tpl.get("name", template_name)):
        raise ValueError(f"Pipeline '{tpl.get('name', template_name)}' already exists")

    lang = normalize_language(language)
    steps: list[PipelineStep] = []
    for s in tpl.get("steps", []):
        if isinstance(s, dict):
            raw_tt = s.get("task_template", "")
            tt = resolve_task_template_localized(raw_tt, language)
            steps.append(PipelineStep(
                department=s.get("department", ""),
                task_template=tt,
                result_key=s.get("result_key"),
                mode=s.get("mode", "deep"),
            ))
    if not steps:
        raise ValueError(f"Pipeline template '{template_name}' has no valid steps")

    var_desc_raw = tpl.get("variable_descriptions") or {}
    var_desc = {str(k): str(v) for k, v in var_desc_raw.items()} if isinstance(var_desc_raw, dict) else {}

    label = tpl.get("label", template_name.replace("-", " ").title())
    desc = tpl.get("description", "")
    if lang == "de":
        label = tpl.get("label_de") or label
        desc = tpl.get("description_de") or desc

    pdef = PipelineDef(
        name=tpl.get("name", template_name),
        label=label,
        description=desc,
        steps=steps,
        variable_descriptions=var_desc,
    )
    runner.upsert_pipeline(pdef)
    return pdef


def render_pipelines_table_markdown(runner: PipelineRunner) -> str:
    """Markdown table for orchestrator persona."""
    pls = runner.pipelines
    if not pls:
        return "_No pipelines defined — add some in `pipelines.yaml` or in the web UI._\n"
    lines = ["| Pipeline | Description | Steps |", "|---|---|---|"]
    for p in pls:
        depts = " → ".join(s.department for s in p.steps)
        desc = (p.description or p.label)[:120]
        lines.append(f"| **`{p.name}`** | {desc} | {depts} |")
    return "\n".join(lines) + "\n"


_PIPELINE_TABLE_BEGIN = "<!-- ORQESTRA_PIPELINE_TABLE_BEGIN -->"
_PIPELINE_TABLE_END = "<!-- ORQESTRA_PIPELINE_TABLE_END -->"


def update_orchestrator_pipeline_file(runner: PipelineRunner, root: Path) -> None:
    """Rewrite the dynamic pipeline table in orchestrator persona files."""
    import re

    block = (
        f"{_PIPELINE_TABLE_BEGIN}\n{render_pipelines_table_markdown(runner)}{_PIPELINE_TABLE_END}"
    )
    for rel in ("personas/orchestrator.md", "personas/orchestrator.de.md"):
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if _PIPELINE_TABLE_BEGIN in text and _PIPELINE_TABLE_END in text:
            text = re.sub(
                re.escape(_PIPELINE_TABLE_BEGIN) + r"[\s\S]*?" + re.escape(_PIPELINE_TABLE_END),
                block,
                text,
                count=1,
            )
        else:
            log.warning("%s missing ORQESTRA_PIPELINE_TABLE markers — skipping pipeline update", rel)
            continue
        path.write_text(text, encoding="utf-8")


def sync_orchestrator_pipeline_tools(engine: Any, runner: PipelineRunner | None, registry: Any) -> None:
    """Add or remove run_pipeline / check_pipeline on the orchestrator engine."""
    mgr = engine.capabilities
    for name in ORCHESTRATOR_PIPELINE_TOOL_NAMES:
        mgr.remove(name)
    if runner is not None and len(registry) > 0:
        mgr.add(runner.create_run_pipeline_capability())
        mgr.add(runner.create_check_pipeline_capability())
    engine.invalidate_tool_schema_cache()
