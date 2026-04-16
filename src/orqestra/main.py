#!/usr/bin/env python3
"""Orqestra — Multi-department business consulting agent.

Entry point: Interactive REPL or single query via --query.

Usage:
    orqestra                          # Interactive REPL
    orqestra --query "Analyze ..."    # Single query
    orqestra --model gpt-4o-mini      # Different model
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
from pathlib import Path

from orqestra._paths import REPO_ROOT as ROOT

from orqestra.core.bootstrap import build_engine, load_config, resolve_env
from orqestra.core.department_builder import DepartmentBuilderSession
from orqestra.core.departments import DepartmentRegistry
from orqestra.core.engine import StrategyEngine
from orqestra.core.display import (
    Spinner,
    print_banner,
    print_departments,
    format_tool_call,
    format_response,
    prompt_string,
    notify_finished_jobs,
    print_job_status,
    print_job_result,
    print_results_list,
    DIM,
    BOLD,
    YELLOW,
    RESET,
)

log = logging.getLogger(__name__)


def _confirm_exit(registry: DepartmentRegistry) -> bool:
    """Ask before exiting if background jobs are still running."""
    active = registry.active_jobs()
    if not active:
        return True
    print(f"\n  {YELLOW}{len(active)} Background-Job(s) laufen noch:{RESET}")
    for j in active:
        preview = j.task.replace("\n", " ")[:60]
        print(f"    {DIM}\u2022 {j.id} ({j.department}): {preview}\u2026{RESET}")
    try:
        answer = input(
            f"  {BOLD}Trotzdem beenden? Jobs werden abgebrochen. (j/N): {RESET}"
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return True
    return answer in ("j", "ja", "y", "yes")


def run_repl(
    engine: StrategyEngine,
    registry: DepartmentRegistry,
    spinner: Spinner,
    cfg: dict,
) -> None:
    print_banner(engine.model)
    print_departments(registry)

    history: list[dict] = []
    job_notified: set[str] = set()

    while True:
        try:
            question = input(prompt_string()).strip()
        except (EOFError, KeyboardInterrupt):
            if not _confirm_exit(registry):
                print()
                continue
            print(f"\n{DIM}Goodbye.{RESET}")
            break

        if len(registry) > 0:
            notify_finished_jobs(registry, job_notified)

        if not question:
            continue
        if question.lower() in ("exit", "quit", "q"):
            if not _confirm_exit(registry):
                continue
            print(f"{DIM}Goodbye.{RESET}")
            break
        if question.lower() == "/new":
            history.clear()
            print(f"\n{DIM}— New conversation —{RESET}\n")
            continue

        if question.lower() == "/status" and len(registry) > 0:
            print_job_status(registry)
            continue

        if question.lower().startswith("/stop"):
            if len(registry) == 0:
                print(f"  {DIM}No departments — nothing to stop.{RESET}\n")
                continue
            parts = question.split(None, 1)
            if len(parts) < 2:
                print(f"  {DIM}Usage: /stop <job_id>  (e.g. /stop seo-1){RESET}\n")
                continue
            job_id = parts[1].strip()
            out = registry.cancel_job(job_id)
            if "error" in out:
                print(f"  {DIM}{out['error']}{RESET}\n")
            else:
                print(f"  {DIM}Stop requested for {out.get('job_id', job_id)}.{RESET}\n")
            continue

        if question.lower().startswith("/results"):
            if len(registry) == 0:
                print(f"  {DIM}No departments.{RESET}\n")
                continue
            parts = question.split()
            if len(parts) == 1:
                print_results_list(registry)
            else:
                job_id = parts[1].strip()
                job = registry.get_job(job_id)
                if not job:
                    print(f"  {DIM}Unknown job: {job_id}{RESET}\n")
                else:
                    print_job_result(job)
            continue

        if question.lower().startswith("/proactive"):
            parts = question.split()
            if len(parts) >= 2 and parts[1].lower() == "trigger":
                from orqestra.core.scheduler import trigger_now
                count = trigger_now(registry)
                print(f"  {DIM}Proaktive Jobs für {count} Departments gestartet.{RESET}\n")
            else:
                print(f"  {DIM}Usage: /proactive trigger{RESET}\n")
            continue

        if question.lower().startswith("/department install"):
            from orqestra.core.department_builder import list_templates, install_template
            parts = question.split()
            if len(parts) < 3:
                templates = list_templates()
                if not templates:
                    print(f"  {DIM}Keine Templates verfügbar.{RESET}\n")
                else:
                    print(f"  {DIM}Verfügbare Templates:{RESET}")
                    for t in templates:
                        desc = t.get("description_de") or t.get("description") or ""
                        print(f"    {t['name']}  —  {t.get('label', '')}  {DIM}{desc[:80]}{RESET}")
                    print(f"  {DIM}Usage: /department install <name>{RESET}\n")
            else:
                tpl_name = parts[2].strip()
                try:
                    engine_cfg = cfg.get("engine") or {}
                    result = install_template(
                        tpl_name,
                        root=ROOT,
                        registry=registry,
                        engine=engine,
                        cfg=cfg,
                        language=engine_cfg.get("language"),
                    )
                    print(f"  {DIM}Department '{result['name']}' installiert ({result.get('label', '')}).{RESET}\n")
                    print_departments(registry)
                except ValueError as e:
                    print(f"  {DIM}Fehler: {e}{RESET}\n")
            continue

        if question.lower() == "/department":
            session = DepartmentBuilderSession(
                engine=engine,
                registry=registry,
                cfg=cfg,
                root=ROOT,
            )
            resp = session.start()
            print(format_response(resp.text))
            while not resp.done:
                try:
                    line = input(f"{DIM}department-builder>{RESET} ").strip()
                except (EOFError, KeyboardInterrupt):
                    print(f"\n{DIM}Department-Generator abgebrochen.{RESET}\n")
                    break
                if not line:
                    continue
                resp = session.advance(line)
                print(format_response(resp.text))
                if resp.created_department:
                    print_departments(registry)
            continue

        active_jobs = registry.active_jobs_info() if len(registry) > 0 else None
        old_len = len(history)
        history = engine.summarize_if_needed(history, active_jobs=active_jobs)
        if len(history) < old_len:
            print(f"  {DIM}(Gespräch zusammengefasst — {old_len} → {len(history)} Nachrichten){RESET}")

        spinner.start("Thinking")
        try:
            answer = engine.run(question, history=history)
        except KeyboardInterrupt:
            spinner.stop()
            print(f"\n{DIM}Interrupted.{RESET}\n")
            continue
        finally:
            spinner.stop()

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})

        print(format_response(answer))


def _start_api_if_enabled(
    cfg: dict,
    *,
    daemon: bool = True,
    engine: StrategyEngine | None = None,
    registry: DepartmentRegistry | None = None,
    pipeline_runner: object | None = None,
) -> threading.Thread | None:
    """Spawn the REST API gateway in a background thread if configured."""
    api_cfg = cfg.get("api") or {}
    if api_cfg.get("enabled") is not True:
        return None

    try:
        from gateway_api import run_api  # noqa: WPS433
    except ImportError:
        log.warning("fastapi/uvicorn not installed \u2014 API gateway disabled.")
        return None

    def _target() -> None:
        try:
            run_api(
                cfg,
                quiet=True,
                engine=engine,
                registry=registry,
                pipeline_runner=pipeline_runner,
            )
        except Exception:
            log.exception("API gateway crashed")

    port = int(api_cfg.get("port", 4200))
    t = threading.Thread(target=_target, name="api-gateway", daemon=daemon)
    t.start()
    log.debug("API gateway started in background on port %d.", port)
    print(f"  {DIM}REST-API l\u00e4uft auf Port {port}.{RESET}")
    web_cfg = cfg.get("web") or {}
    web_index = ROOT / "web" / "dist" / "index.html"
    if web_cfg.get("enabled") is not False and web_index.is_file():
        print(f"  {DIM}Web-UI: http://127.0.0.1:{port}/{RESET}")
    elif web_cfg.get("enabled") is not False and not web_index.is_file():
        print(f"  {DIM}(Web-UI: npm run build in web/ erzeugt web/dist/){RESET}")
    return t


def _start_telegram_if_enabled(
    cfg: dict,
    *,
    daemon: bool = True,
    engine: StrategyEngine | None = None,
    registry: DepartmentRegistry | None = None,
    pipeline_runner: object | None = None,
) -> threading.Thread | None:
    """Spawn the Telegram gateway in a background thread if configured.

    *daemon*: True when running alongside the interactive REPL (thread dies
    with process on exit).  False when the Telegram thread is the only
    foreground activity (``docker compose up`` without TTY) so that
    ``thread.join()`` keeps the process alive.
    """
    tg = cfg.get("telegram") or {}
    if tg.get("enabled") is not True:
        return None

    token = resolve_env(tg.get("token", "${TELEGRAM_BOT_TOKEN}"))
    if not token:
        log.info("Telegram enabled but no token configured \u2014 skipping.")
        return None

    try:
        from gateway_telegram import run_gateway  # noqa: WPS433
    except ImportError:
        log.warning("python-telegram-bot not installed \u2014 Telegram gateway disabled.")
        return None

    def _target() -> None:
        try:
            run_gateway(
                cfg,
                engine=engine,
                registry=registry,
                pipeline_runner=pipeline_runner,
            )
        except Exception:
            log.exception("Telegram gateway crashed")

    t = threading.Thread(target=_target, name="telegram-gateway", daemon=daemon)
    t.start()
    log.info("Telegram gateway started in background.")
    print(f"  {DIM}Telegram-Bot l\u00e4uft im Hintergrund.{RESET}")
    return t


def main() -> None:
    parser = argparse.ArgumentParser(description="Orqestra \u2014 Multi-Department Business Agent")
    parser.add_argument("--query", "-q", help="Single query (non-interactive)")
    parser.add_argument("--model", "-m", help="Override LLM model")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    parser.add_argument(
        "--no-telegram", action="store_true",
        help="Do not start the Telegram gateway even if enabled in config",
    )
    parser.add_argument(
        "--no-web", action="store_true",
        help="Do not serve the web UI (static files from web/dist/) even if enabled in config",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.CRITICAL + 1,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    cfg = load_config()
    if args.no_web:
        cfg.setdefault("web", {})["enabled"] = False
    spinner = Spinner()
    engine, registry, _pipeline_runner = build_engine(cfg, model_override=args.model, spinner=spinner)

    proactive_cfg = cfg.get("proactive") or {}
    if proactive_cfg.get("enabled"):
        from orqestra.core.scheduler import start_scheduler
        start_scheduler(
            registry,
            cron_expr=str(proactive_cfg.get("schedule", "0 6 * * *")),
        )

    interactive = sys.stdin.isatty()
    bg_threads: list[threading.Thread] = []

    if not args.query:
        if not args.no_telegram:
            t = _start_telegram_if_enabled(
                cfg,
                daemon=interactive,
                engine=engine,
                registry=registry,
                pipeline_runner=_pipeline_runner,
            )
            if t:
                bg_threads.append(t)
        t = _start_api_if_enabled(
            cfg,
            daemon=interactive,
            engine=engine,
            registry=registry,
            pipeline_runner=_pipeline_runner,
        )
        if t:
            bg_threads.append(t)

    try:
        if args.query:
            spinner.start("Thinking")
            try:
                answer = engine.run(args.query)
            finally:
                spinner.stop()
            print(answer)
        elif interactive:
            run_repl(engine, registry, spinner, cfg)
        elif bg_threads:
            print(f"  {DIM}Kein interaktives Terminal \u2014 Gateways laufen im Hintergrund.{RESET}")
            print(f"  {DIM}Strg+C zum Beenden.{RESET}")
            try:
                for t in bg_threads:
                    t.join()
            except KeyboardInterrupt:
                print(f"\n{DIM}Shutting down\u2026{RESET}")
        else:
            print("Kein interaktives Terminal und kein Gateway aktiv. Beende.")
            sys.exit(1)
    finally:
        active = registry.active_jobs()
        if active:
            print(f"\n{DIM}Stopping {len(active)} background job(s)\u2026{RESET}")
        registry.shutdown()


if __name__ == "__main__":
    main()
