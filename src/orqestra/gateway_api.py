#!/usr/bin/env python3
"""REST API gateway for Orqestra — REST API and optional web UI (static files from web/dist/).

Run: ``uvicorn orqestra.gateway_api:app`` or ``python -m orqestra.gateway_api`` (after ``pip install -e .``).

Endpoints:
  POST /api/chat              Send a message, get streamed response (SSE)
  POST /api/sessions          Create a new chat session
  DELETE /api/sessions/{id}   Delete a session
  GET  /api/capabilities      List assignable capability names (department builder)
  POST /api/departments/builder/chat   LLM dialog for department builder wizard
  POST /api/departments       Create department (persona + skills + departments.yaml)
  DELETE /api/departments/{name}  Remove department
  GET  /api/departments       List departments + their capabilities
  POST /api/departments/{name}/jobs   Submit a job directly to a department
  GET  /api/jobs              List all jobs
  GET  /api/jobs/export/trajectories  Export job trajectories as JSONL (training data)
  GET  /api/jobs/{id}         Job status + result
  DELETE /api/jobs/{id}       Cancel a running job
  POST /api/upload            Multipart file upload (session + file) — text / vision
"""

from __future__ import annotations

import logging
import sys

from orqestra.core.bootstrap import load_config

from orqestra.api import app, run_api

log = logging.getLogger(__name__)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Orqestra — REST API Gateway")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    cfg = load_config()
    api_cfg = cfg.get("api") or {}
    if api_cfg.get("enabled") is False:
        log.error("api.enabled is false — exiting.")
        sys.exit(1)

    run_api(cfg)


if __name__ == "__main__":
    main()
