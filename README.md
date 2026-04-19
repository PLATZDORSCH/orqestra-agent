# Orqestra

Multi-department business consulting agent with specialized sub-agents, integrated wiki knowledge bases, and proactive multi-phase department jobs.

## Quick start

Three commands and you're up — assumes Docker is installed.

```bash
git clone https://github.com/PLATZDORSCH/orqestra-agent.git
cd orqestra-agent
./scripts/bootstrap.sh        # creates .env + state files (idempotent)
```

Open `.env` and set at least `OPENAI_API_KEY` (any OpenAI-compatible API works — see [Configuration](#configuration) for local models). Then:

```bash
docker compose up -d
```

Open **http://localhost:4200** — the setup wizard collects your project context, the built-in department templates (Market Research, Content Creation, Competitive Intelligence) auto-install on first start.

> Need more detail? Jump to [Installation](#installation), [Configuration](#configuration), or the [docs site](https://orqestra.platzdorsch.io/docs/).

## What is this?

An AI agent system that helps businesses with strategy, SEO, marketing, finance, and operations. It connects to any OpenAI-compatible API and uses a **multi-agent architecture**: an orchestrator routes tasks to specialized departments, each with its own knowledge base, skills, and expertise.

Instead of one monolithic agent, Orqestra runs **departments** — focused sub-agents that build domain-specific knowledge over time. Departments can work autonomously in the background (proactive pipeline), and iterate on complex tasks using **Deep Work** mode.

## Key features

- **Multi-department architecture** — specialized sub-agents with independent knowledge bases
- **Deep Work mode** — iterative execution with structured self-evaluation and progress tracking
- **Proactive pipeline** — per-department **missions** (prompt templates), **strategy** (rotate / random / all), and **cron** schedule; the global `proactive` block in `config.yaml` is the master switch
- **Department templates** — install pre-built departments (Market Research, Content Creation, Competitive Intelligence) with one click
- **Obsidian-style link graph** — force-directed visualization of wiki pages, their links, shared tags and job clusters (not a semantic knowledge graph)
- **FTS5 fuzzy search** — full-text search with fuzzy matching and suggestions
- **i18n personas** — English default with German locale fallback (`.de.md`)
- **Project context** — define your company/project in `project.yaml` to give all agents shared context
- **Four interfaces** — CLI, REST API, Web UI, and Telegram — all sharing the same state

## Architecture

```
User ──▸ Orchestrator ──▸ delegate("seo", "audit example.com")
              │                    ↓
              │              SEO Department
              │              ├── persona (SEO specialist)
              │              ├── knowledge_base/ (own wiki)
              │              ├── skills/ (SEO playbooks)
              │              └── capabilities: analyze_page_seo, axe_wcag_scan, fetch_url
              │
              ├──▸ delegate("strategy", "competitor analysis CRM market")
              │              ↓
              │         Strategy Department
              │         └── capabilities: generate_chart, run_script, read_data
              │
              ├──▸ cross_department_search("keyword research")
              │         → searches ALL department wikis
              │
              └──▸ Proactive Scheduler (APScheduler)
                         → one cron job per department (fallback schedule from config.yaml)
                         → multi-phase proactive jobs (missions or generic prompt)
```

## Deep Work mode

For complex, multi-step tasks, departments can run in **Deep Work** mode:

1. The job runs a **fixed six-phase pipeline** (RESEARCHER / CRITIC / VALIDATOR roles, two cycles) with your task text in each phase.
2. Progress and phase index are shown in the Web UI (e.g. Phase 3/6).
3. Tool calls are tagged with their phase number for traceability.

Use `mode: "deep"` when delegating tasks (API `POST /api/departments/{name}/jobs`, or the Department page **Deep Work** toggle).

## Proactive departments

Departments can work autonomously on a schedule.

### Global switch (`config.yaml`)

```yaml
proactive:
  enabled: true                     # master switch — if false, no scheduler (manual triggers still work)
  schedule: "0 6 * * *"             # default cron when a department has no own schedule
  iterations: 6                     # pipeline phases (Researcher / Critic / Validator), max 6
```

Requires `pip install apscheduler`. The scheduler registers **one cron job per department** that has `proactive.enabled: true` in `departments.yaml`. Each department may set its own `schedule`; otherwise the global `proactive.schedule` above is used.

### Per-department missions (`departments.yaml`)

Optional block:

```yaml
- name: competitive-intel
  label: Competitive Intelligence
  # ... persona, knowledge_base, skills, capabilities ...
  proactive:
    enabled: true
    schedule: "0 6 * * 1"         # optional; omit to use global default
    strategy: rotate               # rotate | random | all
    missions:
      - id: competitor-news
        label: "Competitor news scan"
        prompt: |
          Scan news and PR for our top competitors (see wiki/akteure/…) for the last 7 days.
```

- **strategy `rotate`**: missions run in order; index is persisted in SQLite (`proactive_state` table).
- **strategy `random`**: pick one mission at random each tick.
- **strategy `all`**: enqueue **one job per mission** on each tick.

With **no** `missions` list, the run uses the **generic** proactive prompt (autonomous topic choice), same as before.

**First-time install**: department templates can merge default missions from `templates/proactive_missions/<department-name>.yaml` (see repo).

### Pipeline behaviour

Each proactive job runs the **multi-phase pipeline** (same department LLM, rotating roles): research → critique → … → final `kb_write`. Tool events show roles (`RESEARCHER`, `CRITIC`, `VALIDATOR`) in the Jobs UI. When a mission is selected, its prompt is injected under **Mission (this run)** in phase 1.

### Manual triggers

- All departments (respects per-dept `enabled`): `POST /api/proactive/trigger`, Telegram `/proactive trigger`, CLI (when wired).
- One department: `POST /api/departments/{name}/proactive`, optional query `?mission_id=<id>` for a specific mission.
- **Web UI**: Department page tab **Proactive** (missions + schedule); Jobs page **Proactive run** menu lists default + each mission per department.

### Default mission packs (auto-install)

| Department template | Schedule (example) | Mission ids (summary) |
|---|---|---|
| `competitive-intel` | Weekly Mon 06:00 | competitor-news, positioning-shift, new-entrants, pricing-watch |
| `market-research` | Weekly Mon 06:00 | industry-trends, tam-update, audience-signals, regulation-watch |
| `content-creation` | Daily 06:00 | topic-radar, evergreen-refresh, format-experiments |
| `finanzen` | Monthly 1st 06:00 | cost-anomaly-scan, benchmarks-update, fx-and-rates-watch |
| `wissens-und-contentextraktor` | Daily 06:00 | source-sweep, stale-content-flag |

## Department templates

Three pre-built templates are included:

| Template | Focus |
|---|---|
| **Market Research** | Market trends, target audiences, industry analysis |
| **Content Creation** | Blog posts, social media, newsletters, marketing copy |
| **Competitive Intelligence** | Competitor monitoring, SWOT analysis, market positioning |

Install via:
- **CLI**: `/department install market-research`
- **Web UI**: Templates section in the Department Builder

Templates include English and German personas, so they adapt to your `engine.language` setting.

## Department Builder: starter skills

When you create a department from the Web UI and leave the **skills** step empty, `POST /api/departments` **auto-generates** up to three starter skills from your persona (LLM: `suggest_skills_for_department`, then `generate_skill_content` per suggestion). If generation fails, two generic fallback skills are installed (“Getting started” / “Wiki documentation” in EN, or the German equivalents). You can edit or add skills anytime after creation.

## Project context

On first launch the Web UI shows a **setup wizard** that asks for company, focus areas and target market. Answers are saved to `project.yaml` and injected into the system prompt of every agent.

You can also edit `project.yaml` directly:

```yaml
name: "Acme Corp"
type: "Digital Agency"
location: "Berlin, Germany"
focus: "Web development, AI solutions, e-commerce"
target_market: "SMB in DACH region"
notes: "Focus on privacy-first solutions and local AI"
```

The same form is available any time under **Settings** in the Web UI.

## Capabilities

| Capability | Description |
|---|---|
| `delegate` | Send a task to a department in a **background thread**; returns `job_id` immediately |
| `run_pipeline` | Start a named multi-step pipeline from `pipelines.yaml`; returns `run_id` (poll with `check_pipeline`) |
| `check_job` | Poll status and result for a background job (`job_id`) |
| `check_pipeline` | Poll status of a pipeline run (`run_id` from `run_pipeline`) |
| `cancel_job` | Cooperatively cancel a running background job |
| `cross_department_search` | Search across ALL department knowledge bases |
| `cross_department_read` | Read a full wiki page from a specific department's KB |
| `kb_search` | Full-text search across the knowledge base (FTS5, fuzzy matching) |
| `kb_read` / `kb_write` / `kb_list` / `kb_related` | Wiki CRUD and cross-reference traversal |
| `web_search` | Web search (Brave or SearXNG) |
| `fetch_url` | Chromium-rendered page scraping (JS/SPA support) |
| `analyze_page_seo` | Technical SEO analysis (meta, canonical, JSON-LD, headings) |
| `axe_wcag_scan` | WCAG 2.2 accessibility audit (axe-core) |
| `run_script` | Python execution sandbox |
| `read_data` | Read CSV, Excel, JSON with auto-detection |
| `generate_chart` | Business charts (bar, line, pie, waterfall) |
| `skill_list` / `skill_read` / `skill_create` / `skill_update` | Skill management |

## Installation

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/)

### Setup

```bash
git clone https://github.com/PLATZDORSCH/orqestra-agent.git
cd orqestra-agent
```

Run the bootstrap script once to create `.env` and the YAML state files Docker will bind-mount (without this step Docker would silently turn missing files into empty directories and the app would crash on first start):

```bash
./scripts/bootstrap.sh
```

Open `.env` and set at least your `OPENAI_API_KEY`, then start (Docker builds the image on first run, including the frontend):

```bash
docker compose up -d
```

That's it. The Web UI is available at **http://localhost:4200**.

## Configuration

Orqestra uses these configuration files:

| File | Purpose |
|---|---|
| `config.yaml` | LLM, engine, API, Telegram, proactive schedule … |
| `project.yaml` | Project context (company, market, focus) — editable from the Web UI |
| `departments.yaml` | Department definitions — editable from the Web UI Department Builder or by hand |
| `pipelines.yaml` | Orchestrator pipelines (sequential department chains) — editable from the Web UI **Pipelines** tab or by hand |

On first launch the Web UI shows a **setup wizard** that asks for project context and writes `project.yaml`. You can change everything later under **Settings**. Docker reads these files at startup — restart the container after manual edits (except pipelines/departments, which are usually editable at runtime via the API).

### Departments

On a **fresh install**, if `departments.yaml` is empty, Orqestra **auto-installs** the built-in templates from `templates/` (Market Research, Content Creation, Competitive Intelligence) and populates `departments.yaml` and `departments/`. The orchestrator and shared wiki are always available; you can add more departments at any time:

- **Web UI:** Department Builder at `/departments/new` — a wizard walks you through persona, skills, and capabilities. Pre-built templates are available at the top.
- **CLI:** `/department install market-research` to install a template, or `/department` for the interactive wizard.
- **Manually:** Create or edit `departments.yaml` and restart.

### Pipelines (Orchestrator)

Multi-step workflows that chain several departments together: definitions in `pipelines.yaml`, control via the Web UI under **/pipelines** or via the orchestrator tools **`run_pipeline`** / **`check_pipeline`**. Each step is a normal department job; results can be passed to subsequent steps via `result_key` and `{placeholder}` substitution.

### i18n

Personas support locale fallback:
- Default: `persona.md` (English)
- German: `persona.de.md` (loaded when `engine.language: "German"`)

The orchestrator persona (`personas/orchestrator.md`) also has a German variant (`orchestrator.de.md`).

For web search:

```bash
export BRAVE_API_KEY="..."       # Brave Search
# or
export SEARXNG_URL="http://..."  # Self-hosted SearXNG
```

**Research / `web_search` limits (background jobs):** Each department job shares one budget of **30** `web_search` calls. Identical normalized queries are **deduplicated** (cache hit per job). The tool clamps `count` to **1–10** results per request. Interactive chat (orchestrator / department SSE) does not apply this budget unless a `research_budget` is passed.

## Interfaces

Orqestra has **four interfaces** that can be combined or used independently:

| Interface | Entry point | Config | Default |
|---|---|---|---|
| **CLI** (interactive REPL) | `orqestra` or `python -m orqestra.main` | always available | on (if TTY) |
| **REST API** | `orqestra-api`, `uvicorn orqestra.api.app:app`, or embedded in `orqestra.main` | `api.enabled` | `true` |
| **Web UI** | served from `web/dist/` by the API | `web.enabled` | `true` |
| **Telegram** | `orqestra-telegram` or `python -m orqestra.gateway_telegram` or embedded in `orqestra.main` | `telegram.enabled` | `true` |

### Starting options

**Headless — API + Web + Telegram (recommended for servers):**

```bash
docker compose up -d
```

**Interactive — with the CLI REPL in your terminal:**

```bash
docker compose run --service-ports --rm orqestra
```

> `--service-ports` is required so port 4200 is reachable. The Docker image builds the web frontend automatically (multi-stage build with Node.js).

**Single non-interactive request:**

```bash
docker compose run --rm orqestra orqestra --query "Analyze competitor X"
```

**Additional flags:**

| Flag | Effect |
|---|---|
| `--model gpt-4o-mini` | Override the LLM model |
| `--verbose` / `-v` | Debug logging |
| `--no-telegram` | Disable Telegram (even if enabled in config) |
| `--no-web` | Disable the Web UI |

### Web UI

The React frontend lives in `web/`. When `api.enabled` and `web.enabled` are set in `config.yaml`, the API serves the built static files from `web/dist/` on the same port as the REST API (default: **4200**).

The Dockerfile builds the frontend automatically — no manual step required.

**Development (hot reload, without Docker):**

```bash
cd web && npm run dev     # Vite dev server on port 4201
orqestra                  # API on port 4200 (separate terminal)
```

### Telegram

Long polling — no inbound port required. Shares `config.yaml`, the wiki, and skills with the other interfaces.

#### Setting up the bot

1. **Create a bot:** Open **[@BotFather](https://t.me/BotFather)** in Telegram, send `/newbot`, choose a display name and username. Copy the token.

2. **Configure the token:**
   ```bash
   export TELEGRAM_BOT_TOKEN="your-token-here"
   ```

3. **Restrict access (default):**
   ```yaml
   telegram:
     enabled: true
     token: "${TELEGRAM_BOT_TOKEN}"
     require_whitelist: true
     allowed_user_ids: [123456789]
   ```

4. **Chat commands:** `/new`, `/status`, `/stop <id>`, `/results`, `/proactive`, `/department`, `/cancel`.

### REPL commands

| Command | Description |
|---|---|
| `/new` | Start a new conversation |
| `/status` | List running and recently completed jobs |
| `/stop <job_id>` | Cancel a job |
| `/results` | Summary of completed jobs |
| `/results <job_id>` | Full output of a specific job |
| `/proactive trigger` | Manually trigger proactive jobs for all departments |
| `/department` | Start the department builder wizard |
| `/department install <name>` | Install a template department |
| `exit` / `quit` / `Ctrl+D` | Quit |

## Project structure

Python code lives under **`src/orqestra/`** (installable package `orqestra`). Runtime config and data stay at the repo root.

**HTTP entry (after `pip install -e .`):** `uvicorn orqestra.api.app:app` (recommended) or `uvicorn orqestra.gateway_api:app` (same `app`, thin wrapper module).

```
orqestra/
├── src/orqestra/
│   ├── main.py                  CLI + optional API + Telegram
│   ├── gateway_api.py           REST API standalone entry
│   ├── gateway_telegram.py      Telegram standalone entry
│   ├── api/                     FastAPI app, state, routers (chat, wiki, departments, jobs, pipelines, project, settings, …)
│   ├── core/
│   │   ├── engine.py            StrategyEngine (conversation loop)
│   │   ├── bootstrap.py         build_engine(), config load/save
│   │   ├── registry.py          DepartmentRegistry facade (+ split modules registry_*.py)
│   │   ├── departments.py       Department facade (deep_work, proactive, jobs, …)
│   │   ├── department.py        Department model + shared caps
│   │   ├── deep_work.py         Deep Work 6-phase pipeline
│   │   ├── proactive.py         Proactive prompts
│   │   ├── jobs.py              Job types / events
│   │   ├── pipelines.py         PipelineRunner
│   │   ├── department_builder.py  Wizard + template installer
│   │   ├── scheduler.py         APScheduler
│   │   ├── job_store.py         SQLite job persistence
│   │   ├── capabilities.py      Capability system
│   │   └── display.py           CLI display
│   └── capabilities/
│       ├── knowledge.py         Wiki facade
│       ├── kb_core.py           KnowledgeBase facade (+ kb_fts, kb_base, kb_navigation)
│       ├── kb_capabilities.py   KB tool wiring
│       ├── research.py          Web search + scraping
│       ├── browser_core.py      Playwright/Chromium
│       ├── browser_seo.py       SEO analysis
│       ├── browser_axe.py       WCAG (axe-core)
│       ├── compute.py           Python sandbox
│       ├── data.py              File readers
│       ├── charts.py            Charts
│       ├── files.py             Upload / vision
│       └── skills.py            Skills
├── config.yaml                  LLM, engine, gateway, proactive
├── project.yaml                 Project context (Web UI)
├── departments.yaml             Department definitions
├── pipelines.yaml               Orchestrator pipelines
├── templates/                   Pre-built department templates + `proactive_missions/*.yaml`
├── departments/                 Per-department folders (installed)
├── personas/
├── skills/                      Shared orchestrator skills
├── knowledge_base/              Shared wiki
├── web/                         React frontend (Vite + TypeScript)
├── tests/                       pytest
├── Dockerfile
├── compose.yaml
├── pyproject.toml
└── requirements.txt             delegates to editable install (see pyproject.toml)
```

## Knowledge base (per department)

Each department has its own three-layer wiki:

```
knowledge_base/
├── raw/          Immutable sources (input)
├── wiki/         Structured, interlinked pages (processing)
│   ├── index.md, log.md, memory.md
│   ├── topics/, trends/, regulation/
│   ├── market/, players/, sources/, synthesis/
└── content/      Optional drafts and outputs (template-dependent)
```

Scaffold files (`index.md`, `log.md`, `memory.md`) are created automatically on first run.

## Self-improvement

After completing complex tasks (3+ tool calls), the agent offers to create reusable skills. Skills are versioned and updated based on experience. The agent always asks before creating or modifying a skill — there is no silent self-modification.

## Contributing

Bug reports and pull requests are welcome at <https://github.com/PLATZDORSCH/orqestra-agent>. See `CHANGELOG.md` for release notes.

## License

[MIT](./LICENSE) — Copyright (c) 2026 Tim Dau / PLATZDORSCH Softwareentwicklung
