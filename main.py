#!/usr/bin/env python3
"""Dorsch Agent — Business strategy agent with knowledge base.

Entry point: Interactive REPL or single query via --query.

Usage:
    python main.py                          # Interactive REPL
    python main.py --query "Analyze ..."    # Single query
    python main.py --model gpt-4o-mini      # Different model
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.capabilities import CapabilityManager
from core.engine import StrategyEngine
from capabilities.knowledge import (
    init_knowledge_base,
    kb_search, kb_read, kb_write, kb_list, kb_related,
)
from capabilities.research import web_search, fetch_url
from capabilities.compute import run_script


def load_config() -> dict:
    cfg_path = ROOT / "config.yaml"
    if not cfg_path.exists():
        return {}
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg


def resolve_env(value: str) -> str:
    """Resolve ${ENV_VAR} placeholders in config values."""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        return os.getenv(env_name, "")
    return value


def build_engine(cfg: dict, model_override: str | None = None) -> StrategyEngine:
    llm_cfg = cfg.get("llm", {})
    engine_cfg = cfg.get("engine", {})
    kb_cfg = cfg.get("knowledge_base", {})

    kb_path = Path(kb_cfg.get("path", ROOT / "knowledge_base"))
    if not kb_path.is_absolute():
        kb_path = ROOT / kb_path
    init_knowledge_base(kb_path)

    mgr = CapabilityManager()
    for cap in [kb_search, kb_read, kb_write, kb_list, kb_related,
                web_search, fetch_url, run_script]:
        mgr.add(cap)

    return StrategyEngine(
        base_url=resolve_env(llm_cfg.get("base_url", "https://api.openai.com/v1")),
        api_key=resolve_env(llm_cfg.get("api_key", "${OPENAI_API_KEY}")),
        model=model_override or llm_cfg.get("model", "gpt-4o"),
        capabilities=mgr,
        persona_path=ROOT / "personas" / "strategist.md",
        max_rounds=engine_cfg.get("max_rounds", 25),
    )


def run_repl(engine: StrategyEngine) -> None:
    print("Dorsch Agent — Business Strategy Consultant")
    print("Type 'exit' or Ctrl+D to quit.\n")

    history: list[dict] = []

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit", "q"):
            print("Goodbye.")
            break
        if question.lower() == "/new":
            history.clear()
            print("— New conversation —\n")
            continue

        answer = engine.run(question, history=history)
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})

        print(f"\nDorsch: {answer}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dorsch Agent — Business Strategy Agent")
    parser.add_argument("--query", "-q", help="Single query (non-interactive)")
    parser.add_argument("--model", "-m", help="Override LLM model")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    cfg = load_config()
    engine = build_engine(cfg, model_override=args.model)

    if args.query:
        print(engine.run(args.query))
    else:
        run_repl(engine)


if __name__ == "__main__":
    main()
