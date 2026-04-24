# Changelog

All notable changes to **Orqestra** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] — Env-var resolution for newly created departments

### Fixed
- `create_department_from_builder` (`core/department_builder.py`) and the
  registry reload path used by the departments API
  (`api/departments.py::_registry_reload_params`) now pass `llm.model`
  through `resolve_env()`, just like `llm.base_url` and `llm.api_key`.
  Previously, the raw placeholder string from `config.yaml`
  (e.g. `${OPENAI_MODEL:-gpt-4o-mini}`) was forwarded verbatim to the
  OpenAI client for departments created or reloaded at runtime, causing
  `BadRequestError: Invalid model name passed in model=${OPENAI_MODEL:-gpt-4o-mini}`
  on the first request. Departments built during full engine bootstrap
  were unaffected.
- Default model fallback aligned to `gpt-4o-mini` across all three call
  sites (`bootstrap.py`, `department_builder.py`, `api/departments.py`)
  to match the value documented in `config.yaml` and `.env.example`.

## [0.1.1] — Web UI polish & docs

### Added
- README: new **Quick start** section so new users can clone, bootstrap and
  `docker compose up` in three commands without scrolling.
- Link from the README to the docs site at
  <https://orqestra.platzdorsch.io/docs/>.

### Changed
- Web UI: chat window and department page received layout/UX improvements —
  refined message rendering, spacing, and status indicators
  (`web/src/components/ChatWindow.{tsx,module.css}`,
  `web/src/pages/DepartmentPage.{tsx,module.css}`).
- Orchestrator persona (English + German): tightened wording and corrected
  references to the available departments.
- `templates/pipelines/full-audit.yaml`: minor pipeline adjustment.

## [0.1.0] — Initial public release

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
- `scripts/bootstrap.sh`: idempotent setup script that creates `.env`,
  `project.yaml` and the runtime YAML registries before `docker compose up`,
  preventing Docker from auto-creating empty directories where files are
  expected.

### Changed
- `compose.yaml`: renamed the service from `cod` to `orqestra` and pinned an
  `image: orqestra:latest` tag so commands like
  `docker compose run --rm orqestra ...` from the README work as documented.
- `compose.yaml`: bind-mounts for the YAML config files now use
  `bind: { create_host_path: false }` so a missing host file fails loudly
  instead of silently turning into an empty directory.
- `Dockerfile`: no longer copies `departments/` or `knowledge_base/` into the
  image — they are mounted from the host at runtime so installed departments
  and wiki content are not baked into a public image.
- `README.md`: rewritten in English, real repository URL
  (`https://github.com/PLATZDORSCH/orqestra-agent`) and updated commands
  matching the new compose service name.
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

### Fixed
- Early, actionable error when `departments.yaml` or `pipelines.yaml` is a
  directory instead of a file (the classic Docker bind-mount footgun on a
  fresh clone). `core/registry_yaml.py` and `core/pipelines.py` now raise a
  `RuntimeError` pointing to `scripts/bootstrap.sh`.

### Notes
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

[Unreleased]: https://github.com/PLATZDORSCH/orqestra-agent/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/PLATZDORSCH/orqestra-agent/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/PLATZDORSCH/orqestra-agent/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/PLATZDORSCH/orqestra-agent/releases/tag/v0.1.0
