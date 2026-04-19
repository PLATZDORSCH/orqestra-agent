---
title: "Wiki Scrape"
description: "URL scrapen, Markdown erzeugen und als Rohquelle speichern."
tags: [wiki, knowledge, scraping, web]
version: 1
created: "2026-04-08"
---

# Wiki Scrape

Scrape eine URL, wandle den Inhalt in sauberes Markdown um und speichere ihn als Quelle unter `raw/articles/`.

## Wann nutzen

- Nutzer teilt eine URL und möchte den Inhalt ins Wiki
- „scrape“, „Artikel lesen“, „Quelle hinzufügen“ usw.

## Schritte

1. **URL übernehmen** — Vom Nutzer; bei mehreren URLs nacheinander.

2. **Inhalt holen** — `fetch_url` (standardmäßig Headless-Chromium für JS/SPAs; Playwright siehe README).

3. **Metadaten** — Titel, Autor (falls vorhanden), Datum, URL.

4. **Als Markdown speichern** — `kb_write` nach `raw/articles/YYYY-MM-DD-kurztitel.md`:
   - `title`, `category: sources`, `source_type: article`, `url`, `author`, `published`, `scraped`, `tags`

5. **Nutzer bestätigen** — Titel, Dateiname, ungefähre Wortzahl.

6. **Ingest direkt** — Vollständigen `wiki-ingest`-Workflow ausführen. Ingest ist Standard — nur auslassen, wenn der Nutzer es ausdrücklich will.

## Fallstricke

- Paywall/Login: nicht scrapbar — Nutzer informieren
- Lange Artikel vollständig speichern
- PDFs nicht über diesen Skill — direkt nach `raw/pdfs/`
- Ingest nicht überspringen — sonst bleibt die Quelle unverarbeitet

## Verifikation

Datei in `raw/articles/` mit Metadaten, sauberes Markdown, Ingest-Checks erfüllt, dann Abschluss melden.
