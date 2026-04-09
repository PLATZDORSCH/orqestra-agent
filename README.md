# Dorsch Agent

Business strategy agent with an integrated knowledge base.

## What is this?

An AI agent that helps businesses with strategy, content planning, market analysis, and competitive intelligence. It connects to any OpenAI-compatible API and builds a structured knowledge base over time.

## Capabilities

| Capability | Description |
|---|---|
| `kb_search` | Full-text search across the knowledge base |
| `kb_read` | Read a wiki entry |
| `kb_write` | Create or update a wiki entry |
| `kb_list` | List entries by category or tag |
| `kb_related` | Find linked documents via cross-references |
| `web_search` | Web search (Brave or SearXNG) |
| `fetch_url` | Fetch a web page and extract its content |
| `run_script` | Execute Python scripts for data analysis |

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

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

## Usage

```bash
# Interactive REPL
python main.py

# Single query
python main.py --query "Create a SWOT analysis for company X"

# Different model
python main.py --model gpt-4o-mini

# Debug logging
python main.py --verbose
```

### REPL commands

- `/new` — Start a new conversation
- `exit` / `quit` / `Ctrl+D` — Quit

## Knowledge base

Wiki entries are Markdown files with YAML frontmatter in `knowledge_base/`:

```markdown
---
title: "Company Name"
category: competitors
industry: SaaS
region: DACH
tags: [crm, enterprise]
references:
  - markets/saas-dach.md
---

# Company Name

Content in Markdown ...
```

### Categories

- `companies` — Your own company, clients
- `competitors` — Competing companies
- `markets` — Industries, market segments, regions
- `strategies` — Strategy papers, plans, frameworks

## Project structure

```
dorschagent/
├── core/
│   ├── capabilities.py     # Capability system
│   └── engine.py           # Conversation loop
├── capabilities/
│   ├── knowledge.py        # Knowledge base (FTS5)
│   ├── research.py         # Web research
│   └── compute.py          # Python execution
├── knowledge_base/         # Wiki entries (Markdown)
├── personas/
│   └── strategist.md       # Agent persona
├── config.yaml
├── main.py                 # Entry point
└── requirements.txt
```

## License

MIT
