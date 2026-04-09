# Cod Agent

Business strategy agent with an integrated wiki knowledge base.

## What is this?

An AI agent that helps businesses with strategy, content planning, market analysis, and competitive intelligence. It connects to any OpenAI-compatible API and builds a structured, interlinked knowledge wiki over time — based on the [LLM Wiki Pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

Instead of re-retrieving raw data on every question, the agent **incrementally builds a persistent wiki** — structured, interlinked, compounding. Knowledge is compiled once and kept current.

## How it works

```
URL / file    Share a link or drop a file
                 ↓ Scrape
raw/          Clean markdown sources (immutable)
                 ↓ Ingest
wiki/         Agent builds structured wiki
                 ↓ Draft
content/      Derive publishable content
```

**Three layers:**

| Layer | Who writes | Purpose |
|---|---|---|
| `raw/` | You | Immutable source documents |
| `wiki/` | The agent | Structured, interlinked knowledge base |
| `content/` | The agent (you review) | Blog posts, newsletters, briefings |

## Capabilities

| Capability | Description |
|---|---|
| `kb_search` | Full-text search across the knowledge base (all three layers) |
| `kb_read` | Read a wiki entry, source, or template |
| `kb_write` | Create or update a wiki page |
| `kb_list` | List entries by category or tag |
| `kb_related` | Find linked documents via cross-references |
| `web_search` | Web search (Brave or SearXNG) |
| `fetch_url` | **Chromium by default:** render page, then extract main text (trafilatura); falls back to HTTP if Playwright missing/fails; `use_browser=false` for raw HTTP only |
| `analyze_page_seo` | **Chromium:** full technical SEO — meta, canonical, hreflang, H1–H6, JSON-LD, issues (same browser stack as `fetch_url`) |
| `axe_wcag_scan` | **Chromium + axe-core (Deque):** WCAG 2.2 AA rule tags — violations, incomplete items, help URLs (loads pinned `axe-core` from jsDelivr) |
| `run_script` | Execute Python scripts for calculations, modeling, and data processing |
| `read_data` | Read CSV, Excel, JSON, or text files with auto-detected structure and basic stats |
| `generate_chart` | Create business charts (bar, line, pie, waterfall, stacked, grouped) as PNG |
| `skill_list` | List and search available skills (playbooks) |
| `skill_read` | Read a skill to follow its documented steps |
| `skill_create` | Create a new skill after completing a complex task |
| `skill_update` | Improve an existing skill based on experience |

## Wiki workflows

| Workflow | What happens |
|---|---|
| **Scrape** | Grab a URL → convert to clean markdown, save to `raw/articles/` |
| **Ingest** | Process new source → create summary, update wiki pages, set cross-references |
| **Query** | Ask the wiki → answer from compiled knowledge, not raw data |
| **Lint** | Health check → find contradictions, orphan pages, missing links |
| **Draft** | Create content → derive blog posts, newsletters or briefings from wiki |
| **Newsletter** | Weekly review → automatic summary of recent activity |

Each workflow is documented as a skill in `skills/wiki-*.md`.

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -e .
```

This installs the `cod` command into your PATH. **Recommended for web scraping and SEO:** install the browser stack so `fetch_url` and `analyze_page_seo` use real Chromium instead of plain HTTP:

```bash
pip install -e ".[analysis]"   # pandas, matplotlib, charts, Excel
pip install -e ".[browser]"   # Playwright — then: playwright install chromium
```

Without `browser`, `fetch_url` falls back to HTTP-only fetching (fine for static pages; weak for SPAs). `analyze_page_seo` returns an install hint if Playwright is missing.

## Configuration

Set your API key as an environment variable:

```bash
export OPENAI_API_KEY="sk-..."
```

Or edit `config.yaml`:

```yaml
llm:
  base_url: "https://api.openai.com/v1"
  api_key: "${OPENAI_API_KEY}"
  model: "gpt-4o"
```

For web search, configure one of the supported backends:

```bash
export BRAVE_API_KEY="..."    # Brave Search (2000 requests/month free)
# or
export SEARXNG_URL="http://localhost:8888"  # Self-hosted SearXNG instance
```

### Long-term memory

The agent loads **`knowledge_base/wiki/memory.md`** (body only, no frontmatter) into the system prompt on every request — **keep that file short**. Put detailed analyses in the wiki (e.g. `wiki/synthesis/…`) and **link to them** from memory.

Optional `config.yaml` keys (defaults apply if omitted):

```yaml
memory:
  path: "wiki/memory.md"   # relative to knowledge_base.path
  max_chars: 6000            # max characters of body injected into the prompt
  enabled: true
```

Set `enabled: false` to disable. The agent updates memory via **`kb_write`** (same as any wiki page).

## Usage

### Bare metal

```bash
# Interactive REPL
cod

# Single query
cod --query "Create a SWOT analysis for company X"

# Different model
cod --model gpt-4o-mini

# Debug logging
cod --verbose
```

### Docker

```bash
# Start the interactive REPL in a container
docker compose run --rm cod

# Single query
docker compose run --rm cod --query "Analyze the CRM market"

# Rebuild after code changes
docker compose build
```

The `knowledge_base/` and `skills/` directories are mounted as volumes — changes the agent makes persist on your host filesystem.

Create a `.env` file with your API keys:

```bash
OPENAI_API_KEY=sk-...
BRAVE_API_KEY=...
```

### REPL commands

- `/new` — Start a new conversation
- `exit` / `quit` / `Ctrl+D` — Quit

## Knowledge base structure

```
knowledge_base/
├── raw/                    Immutable source documents (input)
│   ├── articles/           Web articles as Markdown
│   ├── notes/              Personal notes, meeting notes
│   └── pdfs/               PDF documents
├── wiki/                   Structured wiki pages (processing)
│   ├── index.md            Catalog of all pages (agent entry point)
│   ├── log.md              Chronological log of all operations
│   ├── overview.md         Industry overview — the big picture
│   ├── topics/             Domain topics, technologies, methods
│   ├── trends/             Emerging developments and signals
│   ├── regulation/         Laws, standards, compliance
│   ├── market/             Market data, segments, dynamics
│   ├── players/            Companies, associations, people, institutions
│   ├── sources/            One summary per processed source
│   └── synthesis/          Analyses, cross-connections, conclusions
└── content/                Publishable content (output)
    ├── drafts/             Agent-generated drafts (before review)
    ├── published/          Approved, final content
    └── templates/          Templates: blog, briefing, newsletter
```

### Frontmatter

Every wiki page starts with YAML frontmatter:

```yaml
---
title: "AI Agents in Business"
category: topics
created: 2026-04-08
updated: 2026-04-08
tags: [ai, automation, agents]
sources: [2026-04-08-report.md]
status: active
---
```

### Cross-references

The agent maintains bidirectional cross-references between wiki pages. Every page has a "Related Pages" section at the bottom that links to related entries across categories. This makes the knowledge structure visible and navigable (works great with Obsidian's graph view).

## Skills (self-improving playbooks)

Skills are reusable step-by-step procedures stored as Markdown files in `skills/`.

### Wiki skills (built-in)

| Skill | Purpose |
|---|---|
| `wiki-scrape` | Scrape a URL and save as raw source |
| `wiki-ingest` | Process a source and integrate into the wiki |
| `wiki-query` | Answer questions from wiki knowledge |
| `wiki-lint` | Run a health check on the wiki |
| `wiki-draft` | Create publishable content from wiki |
| `wiki-newsletter` | Generate a weekly review |

### Strategy skills

| Skill | Purpose |
|---|---|
| `swot-analysis` | Structured SWOT analysis |
| `competitor-analysis` | Full strategic competitor analysis (positioning, offering, pricing, SWOT) |
| `competitor-deep-dive` | Comprehensive competitor profile |
| `market-sizing` | TAM/SAM/SOM market sizing |
| `business-model-canvas` | Map a business model (9 blocks) |
| `value-proposition-canvas` | Product-market fit analysis (jobs, pains, gains) |
| `pricing-analysis` | Competitive pricing research and tier design |
| `okr-framework` | Define OKRs and KPIs for teams/products |
| `risk-assessment` | Risk identification, scoring, and mitigation planning |

### Finance skills

| Skill | Purpose |
|---|---|
| `financial-forecast` | Revenue and cost projections (12-36 months, multi-scenario) |
| `unit-economics` | CAC, LTV, payback period, LTV/CAC ratio |
| `break-even-analysis` | Break-even point for products, projects, investments |

### Marketing skills

| Skill | Purpose |
|---|---|
| `seo-content-brief` | Research-backed content briefs for search-optimized articles |
| `content-calendar` | 4-12 week content plan with pillars, topics, channels |
| `email-campaign` | Cold outreach, nurture sequences, newsletters |
| `social-media-strategy` | Platform selection, content pillars, posting plan |

### Sales skills

| Skill | Purpose |
|---|---|
| `sales-pitch` | Tailored pitch preparation with objection handling |
| `proposal-generation` | Structured proposals/quotes with scope, timeline, pricing |

### Operations skills

| Skill | Purpose |
|---|---|
| `stakeholder-mapping` | Power/interest grid with engagement strategies |
| `project-kickoff` | Project brief with scope, RACI, timeline, risks |

### Tech skills

| Skill | Purpose |
|---|---|
| `seo-site-audit` | Full technical SEO health check on a website |
| `seo-competitor-analysis` | Reverse-engineer competitor SEO strategy |
| `seo-keyword-research` | Research and prioritize keywords for content strategy |
| `seo-onpage-optimization` | On-page optimization recommendations for a specific page |
| `seo-page-speed` | Page load performance analysis and optimization tips |
| `axe-wcag-accessibility` | Automated a11y audit with axe-core (WCAG 2.2 AA tags) |

The agent **self-improves** by creating new skills after completing complex tasks and updating existing ones with better examples and edge cases.

## Project structure

```
cod-agent/
├── core/
│   ├── capabilities.py     # Capability system
│   ├── engine.py           # Conversation loop
│   └── display.py          # CLI display (spinner, colors, banner)
├── capabilities/
│   ├── knowledge.py        # Knowledge base (FTS5 search, three-layer wiki)
│   ├── research.py         # Web research (Brave, SearXNG, URL extraction)
│   ├── browser_core.py     # Shared Playwright/Chromium session (scrape + SEO)
│   ├── browser_seo.py      # analyze_page_seo — meta, JSON-LD, issues
│   ├── browser_axe.py      # axe_wcag_scan — axe-core WCAG 2.2 AA
│   ├── compute.py          # Python execution sandbox
│   ├── data.py             # Data file reader (CSV, Excel, JSON)
│   ├── charts.py           # Business chart generation (matplotlib)
│   └── skills.py           # Skill management (list, read, create, update)
├── knowledge_base/         # Three-layer wiki (raw → wiki → content)
├── skills/                 # Reusable playbooks (wiki + business skills)
├── personas/
│   └── strategist.md       # Agent persona with wiki rules
├── config.yaml
├── main.py                 # Entry point
├── pyproject.toml          # Package config (provides `cod` command)
├── Dockerfile
├── compose.yaml
└── requirements.txt
```

## License

MIT
