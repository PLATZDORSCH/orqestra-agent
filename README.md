# Orqestra

Multi-department business consulting agent with specialized sub-agents, integrated wiki knowledge bases, and proactive multi-phase department jobs.

## What is this?

An AI agent system that helps businesses with strategy, SEO, marketing, finance, and operations. It connects to any OpenAI-compatible API and uses a **multi-agent architecture**: an orchestrator routes tasks to specialized departments, each with its own knowledge base, skills, and expertise.

Instead of one monolithic agent, Orqestra runs **departments** — focused sub-agents that build domain-specific knowledge over time. Departments can work autonomously in the background (proactive pipeline), and iterate on complex tasks using **Deep Work** mode.

## Key features

- **Multi-department architecture** — specialized sub-agents with independent knowledge bases
- **Deep Work mode** — iterative execution with structured self-evaluation and progress tracking
- **Proactive pipeline** — departments autonomously research and write wiki content on a configurable schedule
- **Department templates** — install pre-built departments (Market Research, Content Creation, Competitive Intelligence) with one click
- **Obsidian-style link graph** — force-directed visualization of wiki pages, their links, shared tags and job clusters (not a semantic knowledge graph)
- **FTS5 fuzzy search** — full-text search with fuzzy matching and suggestions
- **i18n personas** — English default with German locale fallback (`.de.md`)
- **Project context** — define your company/project in `config.yaml` to give all agents shared context
- **Four interfaces** — CLI, REST API, Web UI, and Telegram — all sharing the same state

## Architecture

```
User ──▸ Orchestrator ──▸ delegate("seo", "audit platzdorsch.de")
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
              └──▸ Proactive Scheduler (cron)
                         → departments run multi-phase proactive jobs
```

## Deep Work mode

For complex, multi-step tasks, departments can run in **Deep Work** mode:

1. The job runs a **fixed six-phase pipeline** (RESEARCHER / CRITIC / VALIDATOR roles, two cycles) with your task text in each phase.
2. Progress and phase index are shown in the Web UI (e.g. Phase 3/6).
3. Tool calls are tagged with their phase number for traceability.

Use `mode: "deep"` when delegating tasks (API `POST /api/departments/{name}/jobs`, or the Department page **Deep Work** toggle).

## Proactive departments

Departments can work autonomously on a schedule:

1. **Configure** in `config.yaml`:
   ```yaml
   proactive:
     enabled: true
     schedule: "0 6 * * *"    # cron: daily at 06:00
     iterations: 6            # pipeline phases (Researcher / Critic / Validator), max 6
   ```
2. Each proactive job runs a **multi-phase pipeline** (same department LLM, rotating roles): Recherche → Kritik → Nachrecherche → zweite Kritik → Plausibilität → finale Speicherung mit `kb_write`. Tool events show roles (`RESEARCHER`, `CRITIC`, `VALIDATOR`) in the Jobs UI.
3. **Manual trigger**: CLI `/proactive trigger`, Telegram `/proactive trigger`, or `POST /api/proactive/trigger` (authenticated).

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

## Project context

Beim ersten Öffnen der Web UI erscheint ein **Setup-Wizard**, der nach Unternehmen, Schwerpunkten und Zielmarkt fragt. Die Angaben werden in `project.yaml` gespeichert und in den System-Prompt aller Agents injiziert.

Alternativ `project.yaml` direkt bearbeiten:

```yaml
name: "Acme Corp"
type: "Digital Agency"
location: "Berlin, Germany"
focus: "Web development, AI solutions, e-commerce"
target_market: "SMB in DACH region"
notes: "Focus on privacy-first solutions and local AI"
```

In der Web UI unter **Einstellungen** jederzeit änderbar.

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

### Voraussetzungen

- [Docker](https://docs.docker.com/get-docker/) und [Docker Compose](https://docs.docker.com/compose/)

### Setup

```bash
git clone <repo-url>
cd orqestra
```

```bash
export OPENAI_API_KEY="sk-..."
```

Dann starten (Docker baut das Image beim ersten Mal automatisch, inkl. Frontend):

```bash
docker compose up
```

Das war's. Die Web UI ist danach unter **http://localhost:4200** erreichbar.

## Configuration

Orqestra nutzt diese Konfigurationsdateien:

| Datei | Inhalt |
|---|---|
| `config.yaml` | LLM, Engine, API, Telegram, Proactive-Schedule … |
| `project.yaml` | Projekt-Kontext (Unternehmen, Markt, Fokus) — per Web UI editierbar |
| `pipelines.yaml` | Orchestrierungs-Pipelines (sequenzielle Department-Ketten) — per Web UI **Pipelines** oder manuell |

Beim ersten Öffnen der Web UI fragt ein **Setup-Wizard** den Projekt-Kontext ab und schreibt `project.yaml`. Danach jederzeit unter **Einstellungen** änderbar. Docker liest die Dateien beim Start ein — nach Änderungen Container neu starten (außer Pipelines/Departments, die oft auch per API zur Laufzeit aktualisiert werden).

### Departments

Orqestra starts **without any departments** — on first launch only the orchestrator with its shared knowledge base is available. You can talk to it right away; departments can be added at any time:

- **Web UI:** Department Builder at `/departments/new` — a wizard walks you through persona, skills, and capabilities. Pre-built templates are available at the top.
- **CLI:** `/department install market-research` to install a template, or `/department` for the interactive wizard.
- **Manually:** Create or edit `departments.yaml` and restart.

### Pipelines (Orchestrator)

Mehrstufige Abläufe über mehrere Departments nacheinander: Definitionen in `pipelines.yaml`, Steuerung über die Web UI unter **/pipelines** oder die Orchestrator-Tools **`run_pipeline`** / **`check_pipeline`**. Jeder Schritt ist ein normales Department-Job; Ergebnisse können per `result_key` und `{Platzhalter}` an folgende Schritte weitergereicht werden.

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

## Interfaces

Orqestra has **four interfaces** that can be combined or used independently:

| Interface | Entry point | Config | Default |
|---|---|---|---|
| **CLI** (interactive REPL) | `orqestra` or `python -m orqestra.main` | always available | on (if TTY) |
| **REST API** | `orqestra-api`, `uvicorn orqestra.api.app:app`, or embedded in `orqestra.main` | `api.enabled` | `true` |
| **Web UI** | served from `web/dist/` by the API | `web.enabled` | `true` |
| **Telegram** | `orqestra-telegram` or `python -m orqestra.gateway_telegram` or embedded in `orqestra.main` | `telegram.enabled` | `true` |

### Starting options

**Headless — API + Web + Telegram (empfohlen für Server):**

```bash
docker compose up -d
```

**Interaktiv — mit CLI-REPL im Terminal:**

```bash
docker compose run --service-ports --rm orqestra
```

> `--service-ports` ist nötig, damit Port 4200 erreichbar ist. Das Docker-Image baut das Web-Frontend automatisch (Multi-Stage-Build mit Node.js).

**Einzelne Anfrage (non-interactive):**

```bash
docker compose run --rm orqestra orqestra --query "Analyze competitor X"
```

**Zusätzliche Flags:**

| Flag | Wirkung |
|---|---|
| `--model gpt-4o-mini` | LLM-Modell überschreiben |
| `--verbose` / `-v` | Debug-Logging |
| `--no-telegram` | Telegram deaktivieren (auch wenn in config aktiv) |
| `--no-web` | Web UI deaktivieren |

### Web UI

Das React-Frontend liegt in `web/`. Wenn `api.enabled` und `web.enabled` in `config.yaml` aktiv sind, liefert die API die gebauten statischen Dateien aus `web/dist/` auf demselben Port wie die REST API (Standard: **4200**).

Das Dockerfile baut das Frontend automatisch — kein manueller Schritt nötig.

**Entwicklung (Hot Reload, ohne Docker):**

```bash
cd web && npm run dev     # Vite Dev-Server auf Port 4201
orqestra                  # API auf Port 4200 (separates Terminal)
```

### Telegram

Long Polling — no inbound port needed. Shares `config.yaml`, wiki, and skills with the other interfaces.

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
├── templates/                   Pre-built department templates
├── departments/               Per-department folders (installed)
├── personas/
├── skills/                    Shared orchestrator skills
├── knowledge_base/            Shared wiki
├── web/                       React frontend (Vite + TypeScript)
├── tests/                     pytest
├── Dockerfile
├── compose.yaml
├── pyproject.toml
└── requirements.txt           delegates to editable install (see pyproject.toml)
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

After completing complex tasks (3+ tool calls), the agent offers to create reusable skills. Skills are versioned and updated based on experience.

## License

MIT
