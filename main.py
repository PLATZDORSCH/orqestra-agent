#!/usr/bin/env python3
"""Cod Agent — Business strategy agent with knowledge base.

Entry point: Interactive REPL or single query via --query.

Usage:
    cod                          # Interactive REPL
    cod --query "Analyze ..."    # Single query
    cod --model gpt-4o-mini      # Different model
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml
import frontmatter

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.capabilities import CapabilityManager
from core.engine import StrategyEngine
from core.display import (
    Spinner, print_banner, print_skills,
    format_tool_call, format_response, prompt_string,
    DIM, RESET,
)
from capabilities.knowledge import (
    init_knowledge_base,
    kb_search, kb_read, kb_write, kb_list, kb_related,
)
from capabilities.research import web_search, fetch_url
from capabilities.browser_seo import analyze_page_seo
from capabilities.browser_axe import axe_wcag_scan
from capabilities.compute import run_script
from capabilities.data import read_data
from capabilities.charts import generate_chart
from capabilities.skills import (
    init_skills, get_skills_summary,
    skill_list, skill_read, skill_create, skill_update,
)


def load_config() -> dict:
    cfg_path = ROOT / "config.yaml"
    if not cfg_path.exists():
        return {}
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg


def _load_memory_prompt(kb_path: Path, cfg: dict) -> str | None:
    """Load wiki/memory.md body for system prompt; truncated per config."""
    mem = cfg.get("memory") or {}
    if mem.get("enabled") is False:
        return None
    rel = mem.get("path", "wiki/memory.md")
    max_chars = int(mem.get("max_chars", 6000))
    full = kb_path / rel
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
    """Resolve ${ENV_VAR} placeholders in config values."""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        return os.getenv(env_name, "")
    return value


def build_engine(
    cfg: dict,
    model_override: str | None = None,
    spinner: Spinner | None = None,
) -> StrategyEngine:
    llm_cfg = cfg.get("llm", {})
    engine_cfg = cfg.get("engine", {})
    kb_cfg = cfg.get("knowledge_base", {})

    kb_path = Path(kb_cfg.get("path", ROOT / "knowledge_base"))
    if not kb_path.is_absolute():
        kb_path = ROOT / kb_path
    init_knowledge_base(kb_path)

    skills_cfg = cfg.get("skills", {})
    skills_path = Path(skills_cfg.get("path", ROOT / "skills"))
    if not skills_path.is_absolute():
        skills_path = ROOT / skills_path
    init_skills(skills_path)

    mgr = CapabilityManager()
    for cap in [kb_search, kb_read, kb_write, kb_list, kb_related,
                web_search, fetch_url, analyze_page_seo, axe_wcag_scan, run_script,
                read_data, generate_chart,
                skill_list, skill_read, skill_create, skill_update]:
        mgr.add(cap)

    def on_thinking(msg: str) -> None:
        if spinner:
            spinner.update(msg)

    def on_tool_call(name: str, preview: str) -> None:
        if spinner:
            spinner.stop()
        print(format_tool_call(name, preview))
        if spinner:
            spinner.start(f"Running {name}")

    def on_tool_done() -> None:
        if spinner:
            spinner.stop()

    model = model_override or llm_cfg.get("model", "gpt-4o")

    memory_prompt = _load_memory_prompt(kb_path, cfg)

    return StrategyEngine(
        base_url=resolve_env(llm_cfg.get("base_url", "https://api.openai.com/v1")),
        api_key=resolve_env(llm_cfg.get("api_key", "${OPENAI_API_KEY}")),
        model=model,
        capabilities=mgr,
        persona_path=ROOT / "personas" / "strategist.md",
        memory_prompt=memory_prompt,
        max_rounds=engine_cfg.get("max_rounds", 25),
        language=engine_cfg.get("language"),
        on_thinking=on_thinking,
        on_tool_call=on_tool_call,
        on_tool_done=on_tool_done,
    )


def run_repl(engine: StrategyEngine, spinner: Spinner) -> None:
    print_banner(engine.model)
    print_skills(get_skills_summary())

    history: list[dict] = []

    while True:
        try:
            question = input(prompt_string()).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}Goodbye.{RESET}")
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit", "q"):
            print(f"{DIM}Goodbye.{RESET}")
            break
        if question.lower() == "/new":
            history.clear()
            print(f"\n{DIM}— New conversation —{RESET}\n")
            continue

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Cod Agent — Business Strategy Agent")
    parser.add_argument("--query", "-q", help="Single query (non-interactive)")
    parser.add_argument("--model", "-m", help="Override LLM model")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    cfg = load_config()
    spinner = Spinner()
    engine = build_engine(cfg, model_override=args.model, spinner=spinner)

    if args.query:
        spinner.start("Thinking")
        try:
            answer = engine.run(args.query)
        finally:
            spinner.stop()
        print(answer)
    else:
        run_repl(engine, spinner)


if __name__ == "__main__":
    main()
