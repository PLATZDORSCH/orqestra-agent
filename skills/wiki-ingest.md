---
title: "Wiki Ingest"
description: "Process a new source and integrate the knowledge into the wiki."
tags: [wiki, knowledge, ingest]
version: 1
created: "2026-04-08"
---

# Wiki Ingest

Process a new source and integrate the knowledge into the wiki.

## When to use

- A new file was placed in `raw/`
- User provides a URL or text to process
- User says "ingest", "process", "integrate this", etc.

## Steps

1. **Read the source** — Read the file, scrape the URL, or accept the text.

2. **Check current knowledge** — Read `wiki/index.md` to understand what already exists in the wiki.

3. **Create summary page** — Create a new page in `wiki/sources/` using `kb_write`:
   - Path: `wiki/sources/YYYY-MM-DD-short-title.md`
   - Metadata: title, category=sources, source_type, source_path, tags, created, updated, status=active
   - Content: Summary of key findings, important facts, relevant quotes

4. **Discuss key takeaways** — Briefly list the 3-5 most important takeaways. Ask if the user wants to set priorities.

5. **Update existing wiki pages** — For each relevant existing page:
   - Integrate new information
   - Mark contradictions with `> Warning: Contradiction — ...`
   - Add new cross-references (relative Markdown links)

6. **Create new pages** — If the source contains topics, trends, players, or concepts that don't have their own page yet, create new pages in the appropriate wiki/ subdirectories. Follow frontmatter conventions.

7. **Link related pages** — Every new or updated page needs a "Related Pages" section at the bottom. Links MUST cross category boundaries (see mandatory linking table): Sources link to Topics/Trends/Players, Topics link back to Sources and to related Trends/Players, etc. Links are bidirectional — if A links to B, B MUST link to A. Add back-references to existing pages.

8. **Update index** — Read `wiki/index.md` and verify ALL new pages are listed. Format: `- [Title](path) — Short description (X sources)`

9. **Update overview** — Read `wiki/overview.md` and update it. Incorporate new topics, trends, players, market data. This is NOT optional — always update.

10. **Write log entry** — Append to `wiki/log.md`:
    ```
    ## [YYYY-MM-DD] ingest | Source title
    - Source: raw/articles/filename.md
    - Created: wiki/sources/..., wiki/topics/...
    - Updated: wiki/trends/..., wiki/players/...
    - Summary: Key finding in one sentence.
    ```

## Mandatory linking by page type

| Page type | MUST link to |
|---|---|
| `sources/` | All Topics, Trends, Players, and Regulation pages created or updated from this source |
| `topics/` | Relevant Sources, related Trends, involved Players, affected Regulation |
| `trends/` | Relevant Sources, related Topics, involved Players, affected Regulation |
| `players/` | Relevant Sources, associated Topics, relevant Trends |
| `regulation/` | Relevant Sources, affected Topics, involved Players |
| `market/` | Relevant Sources, related Topics, relevant Trends, relevant Players |
| `synthesis/` | All wiki pages the analysis is based on |

## Pitfalls

- NEVER modify files in `raw/` — they are immutable source documents
- Filenames: lowercase, hyphens, no umlauts or special characters
- A single source can affect 5-15 wiki pages — better to update too many than too few
- Steps 8-10 (Index, Overview, Log) must NEVER be skipped

## Verification

Before reporting completion, check EVERY one of these:

1. Read `wiki/index.md` — are ALL new pages listed? If not: add them NOW.
2. Read `wiki/overview.md` — does it reflect the new findings? If not: update NOW.
3. Read `wiki/log.md` — is there an entry for this ingest? If not: write it NOW.
4. Do all new/updated pages have a "Related Pages" section with cross-category, bidirectional links?
5. Do all new pages have correct YAML frontmatter?
6. Only then report completion to the user.
