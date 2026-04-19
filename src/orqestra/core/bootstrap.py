"""Shared engine setup for CLI, Telegram gateway, and other entry points."""

from __future__ import annotations

import os
from pathlib import Path

import frontmatter
import yaml

from orqestra._paths import REPO_ROOT as ROOT
_env_file = ROOT / ".env"
if _env_file.is_file():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip())

from orqestra.core.capabilities import CapabilityManager
from orqestra.core.departments import (
    DepartmentRegistry,
    load_departments_yaml,
    update_orchestrator_persona_file,
)
from orqestra.core.pipelines import (
    PipelineRunner,
    sync_orchestrator_pipeline_tools,
    update_orchestrator_pipeline_file,
)
from orqestra.core.engine import StrategyEngine

from orqestra.capabilities.knowledge import (  # noqa: E402
    init_knowledge_base,
    init_personal_knowledge_base,
    kb_search,
    kb_read,
    kb_write,
    kb_delete,
    kb_list,
    kb_related,
    my_kb_write,
    my_kb_delete,
    my_kb_list,
    my_kb_related,
)
from orqestra.capabilities.research import web_search, fetch_url  # noqa: E402
from orqestra.capabilities.compute import run_script  # noqa: E402
from orqestra.capabilities.data import read_data  # noqa: E402
from orqestra.capabilities.charts import generate_chart  # noqa: E402
from orqestra.capabilities.skills import (  # noqa: E402
    init_skills,
    skill_list,
    skill_read,
    skill_create,
    skill_update,
)

try:
    from orqestra.capabilities.browser_seo import analyze_page_seo
except ImportError:
    analyze_page_seo = None

try:
    from orqestra.capabilities.browser_axe import axe_wcag_scan
except ImportError:
    axe_wcag_scan = None


def load_config() -> dict:
    cfg_path = ROOT / "config.yaml"
    if not cfg_path.exists():
        return {}
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg


def save_config(cfg: dict) -> None:
    """Write ``config.yaml`` (full replace). Used for UI settings such as ``engine.language``."""
    cfg_path = ROOT / "config.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def load_memory_prompt(kb_path: Path, cfg: dict, *, language: str | None = None) -> str | None:
    """Load wiki/memory.md body for system prompt; truncated per config. Prefers memory.de.md if language is de."""
    from orqestra.core.localization import pick_localized_markdown

    mem = cfg.get("memory") or {}
    if mem.get("enabled") is False:
        return None
    rel = mem.get("path", "wiki/memory.md")
    max_chars = int(mem.get("max_chars", 6000))
    full = kb_path / rel
    full = pick_localized_markdown(full, language)
    if not full.is_file():
        return None
    doc = frontmatter.load(str(full))
    body = (doc.content or "").strip()
    if not body:
        return None
    if len(body) > max_chars:
        body = (
            body[: max_chars - 80].rstrip()
            + "\n\n[… memory truncated — shorten wiki/memory.md or raise memory.max_chars …]"
        )
    return body


def resolve_env(value: str) -> str:
    """Resolve ``${ENV_VAR}`` and ``${ENV_VAR:-default}`` placeholders in config values.

    Posix-style default syntax: when ``ENV_VAR`` is unset *or empty*, ``default`` is used.
    Without a default, an unset/empty variable resolves to ``""``.
    """
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        body = value[2:-1]
        if ":-" in body:
            env_name, default = body.split(":-", 1)
        else:
            env_name, default = body, ""
        return os.getenv(env_name) or default
    return value


PROJECT_YAML = ROOT / "project.yaml"
PROJECT_FIELDS = ("name", "type", "location", "focus", "target_market", "notes")


def load_project() -> dict:
    """Load project context from ``project.yaml`` (preferred) or ``config.yaml`` fallback."""
    if PROJECT_YAML.is_file():
        with open(PROJECT_YAML, encoding="utf-8") as f:
            proj = yaml.safe_load(f) or {}
        if isinstance(proj, dict) and any(proj.get(k) for k in PROJECT_FIELDS):
            return proj
    # Fallback: legacy config.yaml `project:` section
    cfg_path = ROOT / "config.yaml"
    if cfg_path.is_file():
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        proj = cfg.get("project")
        if isinstance(proj, dict) and any(proj.get(k) for k in PROJECT_FIELDS):
            save_project(proj)
            return proj
    return {}


def save_project(proj: dict) -> None:
    """Write project context to ``project.yaml``."""
    clean = {k: proj.get(k, "") for k in PROJECT_FIELDS}
    with open(PROJECT_YAML, "w", encoding="utf-8") as f:
        f.write("# Projekt-Kontext — wird in den System-Prompt aller Agents injiziert.\n")
        f.write("# Bearbeitbar über die Web UI (Einstellungen) oder direkt hier.\n\n")
        yaml.dump(clean, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def build_project_context(cfg: dict) -> str | None:
    """Build a project-context string from ``project.yaml``."""
    proj = load_project()
    if not proj:
        return None
    parts: list[str] = []
    name = proj.get("name")
    if name:
        parts.append(f"You work for **{name}**.")
    for key in ("type", "location", "focus", "target_market", "notes"):
        val = proj.get(key)
        if val:
            parts.append(f"- **{key.replace('_', ' ').title()}**: {val}")
    return "\n".join(parts) if parts else None


def _auto_install_department_templates(root: Path, language: str | None) -> list[dict]:
    """Install all department templates when departments.yaml is empty (first launch)."""
    import logging as _log
    from orqestra.core.department_builder import list_templates

    templates = list_templates()
    if not templates:
        return []
    is_german = language and language.lower().startswith("de")
    from orqestra.core.department_builder import _TEMPLATES_DIR
    from orqestra.core.departments import save_departments_yaml
    from orqestra.core.department import SHARED_CAPS

    installed: list[dict] = []
    for tpl_info in templates:
        tpl_name = tpl_info["name"]
        tpl_dir = _TEMPLATES_DIR / tpl_name
        cfg_path = tpl_dir / "template.yaml"
        if not cfg_path.is_file():
            continue
        with open(cfg_path, encoding="utf-8") as f:
            tpl = yaml.safe_load(f) or {}

        name = tpl.get("name", tpl_name)
        label = tpl.get("label", name.title())
        if is_german:
            label = tpl.get("label_de") or label

        persona_file = "persona.de.md" if is_german and (tpl_dir / "persona.de.md").exists() else "persona.md"
        persona_path = tpl_dir / persona_file
        if not persona_path.exists():
            continue
        persona_content = persona_path.read_text(encoding="utf-8")

        dept_dir = root / "departments" / name
        dept_dir.mkdir(parents=True, exist_ok=True)
        (dept_dir / "persona.md").write_text(persona_content.strip() + "\n", encoding="utf-8")
        (dept_dir / "skills").mkdir(parents=True, exist_ok=True)

        # Copy skills from template
        skills_src = tpl_dir / "skills"
        if skills_src.is_dir():
            import shutil
            for sk_file in sorted(skills_src.glob("*.md")):
                shutil.copy2(sk_file, dept_dir / "skills" / sk_file.name)

        from orqestra.capabilities.knowledge import KnowledgeBase
        KnowledgeBase(dept_dir / "knowledge_base")

        caps_raw = tpl.get("capabilities", [])
        shared_caps = [c for c in caps_raw if c in SHARED_CAPS]

        from orqestra.core.registry import DEFAULT_DEPT_COLORS
        dept_cfg = {
            "name": name,
            "label": label,
            "color": DEFAULT_DEPT_COLORS[len(installed) % len(DEFAULT_DEPT_COLORS)],
            "persona": f"departments/{name}/persona.md",
            "knowledge_base": f"departments/{name}/knowledge_base",
            "skills": f"departments/{name}/skills",
            "capabilities": shared_caps,
        }
        pm_path = root / "templates" / "proactive_missions" / f"{name}.yaml"
        if pm_path.is_file():
            try:
                with open(pm_path, encoding="utf-8") as pmf:
                    proactive_block = yaml.safe_load(pmf) or {}
                if isinstance(proactive_block, dict) and proactive_block:
                    dept_cfg["proactive"] = proactive_block
            except Exception:
                _log.getLogger(__name__).warning(
                    "Skipping invalid proactive mission template: %s", pm_path, exc_info=True,
                )
        installed.append(dept_cfg)

    if installed:
        save_departments_yaml(root, installed)
        _log.getLogger(__name__).info(
            "Auto-installed %d department template(s): %s",
            len(installed),
            ", ".join(d["name"] for d in installed),
        )
    return installed


def _auto_install_pipeline_templates(
    runner: PipelineRunner,
    available_dept_names: set[str],
    language: str | None,
) -> list[str]:
    """Install pipeline templates from templates/pipelines/ when pipelines.yaml is empty."""
    import logging as _log

    from orqestra.core.pipelines import install_pipeline_template, list_pipeline_templates

    if runner.pipelines:
        return []
    installed: list[str] = []
    for tpl in list_pipeline_templates():
        required = set(tpl.get("required_departments") or [])
        if required and not required.issubset(available_dept_names):
            continue
        try:
            install_pipeline_template(tpl["name"], runner, language=language)
            installed.append(tpl["name"])
        except ValueError:
            pass
    if installed:
        _log.getLogger(__name__).info(
            "Auto-installed %d pipeline template(s): %s",
            len(installed),
            ", ".join(installed),
        )
    return installed


def build_engine(
    cfg: dict,
    model_override: str | None = None,
    spinner: object | None = None,
    *,
    headless: bool = False,
) -> tuple[StrategyEngine, DepartmentRegistry, PipelineRunner]:
    """Build orchestrator StrategyEngine, DepartmentRegistry, and PipelineRunner.

    *headless*: no CLI spinner or print callbacks (for Telegram gateway etc.).
    """
    from orqestra.core.display import format_tool_call

    llm_cfg = cfg.get("llm", {})
    engine_cfg = cfg.get("engine", {})
    kb_cfg = cfg.get("knowledge_base", {})

    base_url = resolve_env(llm_cfg.get("base_url", "https://api.openai.com/v1"))
    api_key = resolve_env(llm_cfg.get("api_key", "${OPENAI_API_KEY}"))
    model = model_override or resolve_env(llm_cfg.get("model", "gpt-4o-mini"))
    language = engine_cfg.get("language")

    kb_path = Path(kb_cfg.get("path", ROOT / "knowledge_base"))
    if not kb_path.is_absolute():
        kb_path = ROOT / kb_path
    main_kb = init_knowledge_base(kb_path)

    pk_cfg = cfg.get("personal_knowledge") or {}
    personal_kb_enabled = pk_cfg.get("enabled", True)
    if personal_kb_enabled:
        pk_path = Path(pk_cfg.get("path", ROOT / "personal_knowledge"))
        if not pk_path.is_absolute():
            pk_path = ROOT / pk_path
        init_personal_knowledge_base(pk_path)

    skills_cfg = cfg.get("skills", {})
    skills_path = Path(skills_cfg.get("path", ROOT / "skills"))
    if not skills_path.is_absolute():
        skills_path = ROOT / skills_path
    init_skills(skills_path)
    from orqestra.capabilities.skills import set_skill_read_language

    set_skill_read_language(language)

    if headless:

        def on_thinking(msg: str, _preview: str = "") -> None:
            return

        def on_tool_call(name: str, preview: str, fn_args: dict | None = None) -> None:
            return

        def on_tool_done() -> None:
            return

    else:

        def on_thinking(msg: str, _preview: str = "") -> None:
            if spinner:
                spinner.update(msg)

        def on_tool_call(name: str, preview: str, fn_args: dict | None = None) -> None:
            if spinner:
                spinner.stop()
            print(format_tool_call(name, preview))
            if spinner:
                spinner.start(f"Running {name}")

        def on_tool_done() -> None:
            if spinner:
                spinner.stop()

    from orqestra.core.job_store import JobStore
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    job_store = JobStore(data_dir / "jobs.db")

    jobs_cfg = cfg.get("jobs") or {}
    max_workers = int(jobs_cfg.get("max_workers", 5))
    max_queued = int(jobs_cfg.get("max_queued", 20))
    registry = DepartmentRegistry(max_workers=max_workers, max_queued=max_queued)
    departments_cfg = load_departments_yaml(ROOT)
    project_context = build_project_context(cfg)
    if not departments_cfg:
        departments_cfg = _auto_install_department_templates(ROOT, language)
    if departments_cfg:
        registry.build(
            departments_cfg,
            root=ROOT,
            llm_base_url=base_url,
            llm_api_key=api_key,
            llm_model=model,
            language=language,
            context_window=int(engine_cfg.get("context_window", 0)),
            summarize_at=float(engine_cfg.get("summarize_at", 0.7)),
            project_context=project_context,
        )
    registry.set_job_store(job_store)
    proactive_cfg = cfg.get("proactive") or {}
    registry.set_proactive_iterations(int(proactive_cfg.get("iterations", 6)))

    pipeline_runner = PipelineRunner(ROOT, registry, job_store)
    if not pipeline_runner.pipelines and departments_cfg:
        available = {d.get("name") for d in departments_cfg if d.get("name")}
        _auto_install_pipeline_templates(pipeline_runner, available, language)

    mgr = CapabilityManager()

    orchestrator_caps: list = [
        kb_search,
        kb_read,
        kb_write,
        kb_delete,
        kb_list,
        kb_related,
    ]
    if personal_kb_enabled:
        orchestrator_caps.extend(
            [my_kb_write, my_kb_delete, my_kb_list, my_kb_related],
        )
    orchestrator_caps.extend(
        [
            web_search,
            fetch_url,
            run_script,
            read_data,
            generate_chart,
            skill_list,
            skill_read,
            skill_create,
            skill_update,
        ],
    )
    for cap in orchestrator_caps:
        mgr.add(cap)

    if analyze_page_seo:
        mgr.add(analyze_page_seo)
    if axe_wcag_scan:
        mgr.add(axe_wcag_scan)

    if len(registry) > 0:
        mgr.add(registry.create_delegate_capability())
        mgr.add(registry.create_cross_search_capability())
        mgr.add(registry.create_cross_read_capability())
        mgr.add(registry.create_check_job_capability())
        mgr.add(registry.create_cancel_job_capability())

    memory_prompt = load_memory_prompt(kb_path, cfg, language=language)
    project_context = build_project_context(cfg)

    orchestrator = StrategyEngine(
        base_url=base_url,
        api_key=api_key,
        model=model,
        capabilities=mgr,
        persona_path=ROOT / "personas" / "orchestrator.md",
        memory_prompt=memory_prompt,
        project_context=project_context,
        max_rounds=engine_cfg.get("max_rounds", 90),
        language=language,
        context_window=int(engine_cfg.get("context_window", 0)),
        summarize_at=float(engine_cfg.get("summarize_at", 0.7)),
        on_thinking=on_thinking,
        on_tool_call=on_tool_call,
        on_tool_done=on_tool_done,
    )

    sync_orchestrator_pipeline_tools(orchestrator, pipeline_runner, registry)
    update_orchestrator_persona_file(registry, ROOT)
    update_orchestrator_pipeline_file(pipeline_runner, ROOT)
    orchestrator.invalidate_persona()

    return orchestrator, registry, pipeline_runner
