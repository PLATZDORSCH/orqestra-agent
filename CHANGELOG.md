# Changelog

All notable changes to **Orqestra** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `LICENSE` (MIT) at the repository root.
- `CHANGELOG.md` (this file).
- `.env.example`: documents `OPENAI_BASE_URL` and `OPENAI_MODEL` so users
  can switch the LLM endpoint and model without touching `config.yaml`.
- `resolve_env()` now supports the Posix-style default syntax
  `${VAR:-default}`, so `config.yaml` can carry sensible fallbacks and the
  same file works whether the env vars are set or not.
- `compose.yaml`: `ports: ["4200:4200"]`, `TELEGRAM_BOT_TOKEN` env passthrough,
  and host volume mounts for `data/`, `departments/`, `knowledge_base/`,
  `skills/`, `config.yaml`, `project.yaml`, `departments.yaml` and
  `pipelines.yaml` so user data and configuration survive container rebuilds.
- `GET /api/version` endpoint returning the running package version, Python
  version and platform.
- `.github/CODEOWNERS` so every PR requires a maintainer review.
- `.github/workflows/release.yml`: tag-triggered GitHub Release with auto
  generated notes.
- Single source of truth for the version: `orqestra.__version__` is read from
  the installed package metadata (`importlib.metadata`), the FastAPI app and
  `/api/version` use it.

### Changed
- `compose.yaml`: renamed the service from `cod` to `orqestra` and pinned an
  `image: orqestra:latest` tag so commands like
  `docker compose run --rm orqestra ...` from the README work as documented.
- `Dockerfile`: no longer copies `departments/` or `knowledge_base/` into the
  image — they are mounted from the host at runtime so installed departments
  and wiki content are not baked into a public image.
- `README.md`: rewritten in English, real repository URL
  (`https://github.com/PLATZDORSCH/orqestra-agent`) and updated commands matching
  the new compose service name.
- `web/package.json`: bumped version `0.0.0` → `0.1.0` to match the Python
  package.
- `config.yaml`: `llm.base_url` and `llm.model` are now resolved from
  `${OPENAI_BASE_URL:-https://api.openai.com/v1}` and
  `${OPENAI_MODEL:-gpt-4o-mini}` — no provider-specific values are baked
  into the file shipped with the repo.
- `compose.yaml`: forwards `OPENAI_BASE_URL` and `OPENAI_MODEL` to the
  container.
- `.gitignore`: substantially expanded to keep user-generated content out of
  the public repo (FTS indexes, per-department wikis, `data/`, `output/`,
  `personal_knowledge/`, `project.yaml`, IDE/OS junk, build artefacts).

## [0.1.0] — Initial public release

First public version of Orqestra:

- Multi-department orchestrator with delegated background jobs.
- Six-phase Deep Work pipeline (RESEARCHER / CRITIC / VALIDATOR roles).
- Per-department proactive missions with cron schedules and rotate / random
  / all strategies.
- Department templates: Market Research, Content Creation, Competitive
  Intelligence (English + German personas).
- FTS5 full-text search across per-department wikis with fuzzy matching.
- Obsidian-style link-graph visualization of the wiki.
- Four interfaces sharing one state: CLI, REST API, React Web UI, Telegram.
- Skill system (`skill_list` / `skill_read` / `skill_create` / `skill_update`)
  with versioning; agents propose new or updated skills after multi-step
  tasks but never modify them silently.
- Capabilities: `web_search` (Brave / SearXNG), `fetch_url` (Playwright),
  `analyze_page_seo`, `axe_wcag_scan`, `run_script`, `read_data`,
  `generate_chart`, KB CRUD and cross-department search.

[Unreleased]: https://github.com/PLATZDORSCH/orqestra-agent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/PLATZDORSCH/orqestra-agent/releases/tag/v0.1.0
