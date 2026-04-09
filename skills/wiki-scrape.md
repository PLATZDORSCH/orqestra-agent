---
title: "Wiki Scrape"
description: "Scrape a URL, convert to Markdown, and save as a raw source."
tags: [wiki, knowledge, scraping, web]
version: 1
created: "2026-04-08"
---

# Wiki Scrape

Scrape a URL, convert the content to clean Markdown, and save it as a source in `raw/articles/`.

## When to use

- User shares a URL and wants the content added to the wiki
- User says "scrape this", "read this article", "add this source", etc.
- User shares a link via any interface

## Steps

1. **Receive URL** — Take the URL from the user. If multiple URLs: process them one at a time.

2. **Fetch content** — Use `fetch_url` to retrieve the page and extract clean content (by default **headless Chromium** renders the page first, so JS/SPA sites work; ensure Playwright is installed — see project README):
   - HTML boilerplate is removed automatically (navigation, footer, ads, cookie banners)
   - Main article body is extracted
   - Headings, lists, links, and code blocks are preserved

3. **Extract metadata** — From the page, extract:
   - Title
   - Author (if available)
   - Publication date (if available)
   - URL as source reference

4. **Save as Markdown** — Use `kb_write` to save in `raw/articles/`:
   - Path: `raw/articles/YYYY-MM-DD-short-title.md`
   - Filenames: lowercase, hyphens, no special characters
   - Metadata fields:
     - `title`: Original article title
     - `category`: sources
     - `source_type`: article
     - `url`: The original URL
     - `author`: Author name (if found)
     - `published`: Publication date (if found)
     - `scraped`: Today's date
     - `tags`: Relevant topic tags

5. **Confirm to user** — Report title, filename, and approximate word count.

6. **Run ingest** — Immediately execute the full wiki-ingest workflow (steps 1-10 from wiki-ingest). Ingest is the DEFAULT — only skip if the user explicitly says not to. Scrape without ingest is an incomplete job.

## Pitfalls

- Paywalled or login-protected pages cannot be scraped — inform the user
- Save long articles in full, don't truncate — trimming happens during ingest
- PDFs should not go through this skill — place them directly in `raw/pdfs/`
- NEVER skip the ingest step — scrape without ingest leaves the source unprocessed in raw/

## Verification

Before reporting completion, check ALL of these:

1. Markdown file exists in `raw/articles/` with correct metadata
2. Content is clean Markdown without HTML artifacts
3. Filename follows the `YYYY-MM-DD-short-title.md` convention
4. If ingest was run: ALL ingest verification points pass (index.md, overview.md, log.md, cross-references)
5. Only then report completion to the user.
