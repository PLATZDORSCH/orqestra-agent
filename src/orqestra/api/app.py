"""FastAPI application: CORS, lifespan, route registration."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from orqestra import __version__
from orqestra.core.bootstrap import load_config

from orqestra.api.chat import router as chat_router
from orqestra.api.departments import router as departments_router
from orqestra.api.jobs import router as jobs_router
from orqestra.api.pipelines import router as pipelines_router
from orqestra.api.project import router as project_router
from orqestra.api.settings import router as settings_router
from orqestra.api.sessions import router as sessions_router
from orqestra.api.state import mount_web_ui, state
from orqestra.api.version import router as version_router
from orqestra.api.wiki import router as wiki_router

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared state when the ASGI app starts without ``run_api()`` (e.g. ``uvicorn``).

    ``run_api(cfg)`` calls ``state.init(cfg, …)`` with an explicit config; the lifespan
    path loads config via ``load_config()`` and is a no-op if ``state`` is already
    ready. Both paths call ``mount_web_ui``; ``_web_ui_mounted`` prevents double mounts.
    """
    if not state._ready:
        state.init(load_config())
    mount_web_ui(state._cfg, quiet=False)
    yield


app = FastAPI(title="Orqestra API", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # Browsers disallow credentials with wildcard origins; API auth uses Authorization: Bearer.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# departments_router before chat_router: /api/departments/builder/chat must not be
# captured by /api/departments/{name}/chat (name="builder").
app.include_router(version_router)
app.include_router(sessions_router)
app.include_router(wiki_router)
app.include_router(departments_router)
app.include_router(chat_router)
app.include_router(jobs_router)
app.include_router(pipelines_router)
app.include_router(project_router)
app.include_router(settings_router)
