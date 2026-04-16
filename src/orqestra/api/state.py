"""Mutable API singleton: engine, registry, sessions, knowledge base."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from orqestra.core.bootstrap import build_engine, resolve_env
from orqestra.core.departments import DepartmentRegistry
from orqestra.core.pipelines import PipelineRunner
from orqestra.core.engine import StrategyEngine

from orqestra.api.constants import ROOT

if TYPE_CHECKING:
    from orqestra.capabilities.knowledge import KnowledgeBase

log = logging.getLogger(__name__)


@dataclass
class WebSession:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    history: list[dict] = field(default_factory=list)
    last_seen: float = field(default_factory=time.time)


SESSION_IDLE_SECONDS = 24 * 3600


class _State:
    """Mutable singleton shared across request handlers."""

    engine: StrategyEngine
    registry: DepartmentRegistry
    pipeline_runner: PipelineRunner
    sessions: dict[str, WebSession]
    api_token: str | None
    dept_chat_histories: dict[str, list[dict]]
    main_kb: "KnowledgeBase"
    personal_kb: "KnowledgeBase | None"
    _cfg: dict

    def __init__(self) -> None:
        self.sessions = {}
        self.dept_chat_histories = {}
        self.api_token = None
        self._ready = False
        self._cfg = {}
        self.personal_kb = None

    def init(
        self,
        cfg: dict,
        *,
        engine: StrategyEngine | None = None,
        registry: DepartmentRegistry | None = None,
        pipeline_runner: PipelineRunner | None = None,
    ) -> None:
        """Load engine + department registry. Safe to call multiple times (idempotent).

        When *engine*, *registry*, and *pipeline_runner* are provided (embedded
        mode from ``main.py``), the API shares the same runtime objects as the
        REPL instead of building a second, disconnected stack.
        """
        if self._ready:
            return
        self._cfg = cfg
        if engine and registry and pipeline_runner:
            self.engine = engine
            self.registry = registry
            self.pipeline_runner = pipeline_runner
        else:
            self.engine, self.registry, self.pipeline_runner = build_engine(cfg, headless=True)
        api_cfg = cfg.get("api") or {}
        token = resolve_env(api_cfg.get("auth_token", "${ORQESTRA_API_TOKEN}"))
        self.api_token = token if token else None
        from orqestra.capabilities.knowledge import KnowledgeBase

        kb_cfg = cfg.get("knowledge_base") or {}
        kb_path = kb_cfg.get("path", ROOT / "knowledge_base")
        kb_path = kb_path if isinstance(kb_path, Path) else Path(kb_path)
        if not kb_path.is_absolute():
            kb_path = ROOT / kb_path
        self.main_kb = KnowledgeBase(kb_path)
        self.main_kb.department_links = []

        pk_cfg = cfg.get("personal_knowledge") or {}
        if pk_cfg.get("enabled", True):
            pk_path = pk_cfg.get("path", ROOT / "personal_knowledge")
            pk_path = pk_path if isinstance(pk_path, Path) else Path(pk_path)
            if not pk_path.is_absolute():
                pk_path = ROOT / pk_path
            self.personal_kb = KnowledgeBase(pk_path)
        else:
            self.personal_kb = None
        from orqestra.api.wiki import sync_department_links

        sync_department_links()
        self.main_kb.refresh_navigation_pages()
        proactive_cfg = cfg.get("proactive") or {}
        self.registry.set_proactive_iterations(int(proactive_cfg.get("iterations", 6)))
        if proactive_cfg.get("enabled"):
            from orqestra.core.scheduler import start_scheduler

            start_scheduler(
                self.registry,
                cron_expr=str(proactive_cfg.get("schedule", "0 6 * * *")),
            )
        self._ready = True

    def prune_stale(self) -> None:
        now = time.time()
        stale = [
            sid for sid, s in self.sessions.items()
            if now - s.last_seen > SESSION_IDLE_SECONDS
        ]
        for sid in stale:
            del self.sessions[sid]

    def get_session(self, sid: str) -> WebSession | None:
        s = self.sessions.get(sid)
        if s:
            s.last_seen = time.time()
        return s

    def get_or_create_session(self, sid: str) -> WebSession:
        """Return existing session or transparently create a new one (survives server restarts)."""
        s = self.sessions.get(sid)
        if s:
            s.last_seen = time.time()
            return s
        s = WebSession(id=sid)
        self.sessions[sid] = s
        return s


state = _State()

_web_ui_mounted = False


def sync_orchestrator_pipeline_artifacts() -> None:
    """Refresh pipeline tools + orchestrator.md pipeline table (e.g. after department changes)."""
    from orqestra.core.pipelines import sync_orchestrator_pipeline_tools, update_orchestrator_pipeline_file

    sync_orchestrator_pipeline_tools(state.engine, state.pipeline_runner, state.registry)
    update_orchestrator_pipeline_file(state.pipeline_runner, ROOT)
    state.engine.invalidate_persona()


def check_auth(request: object) -> None:
    from fastapi import HTTPException

    if not state.api_token:
        return
    auth = request.headers.get("authorization", "")
    if auth == f"Bearer {state.api_token}":
        return
    raise HTTPException(status_code=401, detail="Unauthorized")


def mount_web_ui(cfg: dict, *, quiet: bool = False) -> None:
    """Serve the built React app from web/dist/ (optional, after all /api routes)."""
    from fastapi import HTTPException
    from starlette.responses import FileResponse
    from starlette.staticfiles import StaticFiles

    from orqestra.api.app import app

    global _web_ui_mounted
    if _web_ui_mounted:
        return
    web_cfg = cfg.get("web") or {}
    if web_cfg.get("enabled") is False:
        _web_ui_mounted = True
        return
    web_dist = ROOT / "web" / "dist"
    index = web_dist / "index.html"
    if not index.is_file():
        if not quiet:
            log.info("Web UI dist missing (run npm run build in web/) — skipping static serving.")
        _web_ui_mounted = True
        return
    assets_dir = web_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="web-assets")

    @app.get("/")
    async def serve_web_root() -> FileResponse:
        return FileResponse(index)

    @app.get("/{full_path:path}")
    async def serve_web_spa(full_path: str) -> FileResponse:
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="Not found")
        try:
            candidate = (web_dist / full_path).resolve()
            candidate.relative_to(web_dist.resolve())
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found") from None
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)

    _web_ui_mounted = True
    if not quiet:
        log.info("Serving web UI from %s", web_dist)


def run_api(
    cfg: dict,
    *,
    quiet: bool = False,
    engine: StrategyEngine | None = None,
    registry: DepartmentRegistry | None = None,
    pipeline_runner: PipelineRunner | None = None,
) -> None:
    """Start the API server (blocking). Call from a thread or as main."""
    import uvicorn

    from orqestra.api.app import app

    state.init(
        cfg,
        engine=engine,
        registry=registry,
        pipeline_runner=pipeline_runner,
    )
    api_cfg = cfg.get("api") or {}
    host = api_cfg.get("host", "0.0.0.0")
    port = int(api_cfg.get("port", 4200))

    from orqestra.api.constants import QUIET_UVICORN_LOG_CONFIG

    log_config: dict | None = QUIET_UVICORN_LOG_CONFIG if quiet else uvicorn.config.LOGGING_CONFIG

    uv_config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="critical" if quiet else "info",
        access_log=not quiet,
        log_config=log_config,
    )
    server = uvicorn.Server(uv_config)

    if not quiet:
        log.info("Starting API gateway on %s:%d", host, port)

    mount_web_ui(cfg, quiet=quiet)

    server.run()
