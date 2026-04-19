---
title: "Wiki Ingest"
description: "Rohquelle ins Wiki übernehmen — Entitäten extrahieren, in die richtigen Ordner verteilen, verknüpfen."
tags: [wiki, knowledge-management]
version: 3
created: "2026-04-08"
updated: "2026-04-15"
---

# Wiki Ingest

Verarbeite eine Rohquelle und lege strukturierte Wiki-Einträge in den passenden Ordnern an.

## Wann nutzen

- Nutzer liefert URL, Dokument oder Text für die Wissensbasis
- Aufbau von Domänenwissen aus externen Quellen
- Nach einem `wiki-scrape` — Ingest ist immer der nächste Schritt
- Nach Analyse, Audit oder Recherche mit neuem Wissen

## Wiki-Ordnerstruktur (vier Ordner)

Jede Wissensbasis (Orchestrator und Departments) nutzt dasselbe Layout. **Vier Ordner** halten Inhalte für Menschen und Agenten nachvollziehbar:

| Ordner | `category` in YAML | Inhalt | Beispiel-Dateinamen |
|---|---|---|---|
| `wiki/akteure/` | `akteure` | Unternehmen, Wettbewerber, Personen, Organisationen — **eine Seite pro Entität** | `acme-corp.md`, `google.md`, `john-doe.md` |
| `wiki/recherche/` | `recherche` | Quellenzusammenfassungen, Recherche-Notizen, Takeaways aus Quellen | `2026-04-10-gartner-report.md` |
| `wiki/wissen/` | `wissen` | Dauerhaftes Referenzwissen: Themen, Trends, Marktfakten, Regeln, Frameworks — alles, was du langfristig behältst | `saas-markt-dach.md`, `dsgvo-updates.md`, `seo-grundlagen.md` |
| `wiki/ergebnisse/` | `ergebnisse` | Fertige Deliverables: Analysen, Vergleiche, Strategie-Outputs, übergreifende Synthesen zu einem Projekt oder Ingest | `wettbewerbsanalyse-2026-04.md`, `swot-acme.md` |

Schütte **nicht** alles nach `wiki/ergebnisse/` — nutze `akteure/` für Entitäten, `recherche/` für „was wir gelesen haben“, `wissen/` für wiederverwendbare Fakten und Konzepte.

### Frontmatter-Konventionen pro Ordner

**`wiki/akteure/`** — Entitätsseiten:
```yaml
title: "ACME Corp"
category: akteure
tags: [competitor, saas, dach]
url: "https://acme.com"       # Website der Firma/Organisation
status: active                 # active | inactive | acquired
```

**`wiki/recherche/`** — Quellenzusammenfassungen:
```yaml
title: "Gartner Magic Quadrant 2026"
category: recherche
tags: [gartner, market-research]
url: "https://..."             # Original-URL
source_type: report            # report | article | study | presentation
published: "2026-03-15"       # Erscheinungsdatum der Originalquelle
```

**`wiki/wissen/`** — Referenzwissen:
```yaml
title: "SaaS-Markt DACH 2026"
category: wissen
tags: [saas, dach, marktgröße]
```

**`wiki/ergebnisse/`** — Analysen / Deliverables:
```yaml
title: "Wettbewerbsanalyse Q2 2026"
category: ergebnisse
tags: [wettbewerb, analyse]
```

Alle Seiten erhalten `created` und `updated` automatisch über `kb_write`.

## Schritte

1. **Quelle holen** — `fetch_url` für Webinhalte oder `read_data` für Dateien. Liegt die Quelle schon in `raw/`, mit `kb_read` lesen.

2. **Rohspeicher** — Original als `raw/articles/YYYY-MM-DD-title.md` ablegen (unveränderliches Archiv). Überspringen, falls `wiki-scrape` das schon getan hat.

3. **Entitäten extrahieren** — Quelle sorgfältig lesen und **alles** davon identifizieren:
   - **Akteure**: genannte Unternehmen, Wettbewerber, Personen, Organisationen
   - **Wissen**: Marktdaten, Trends, Regeln, Frameworks, dauerhafte Fakten
   - **Kernaussagen**: wichtige Aussagen mit Zahlen

4. **Auf Wiki-Ordner verteilen** — Für **jede** Entität oder jedes Wissensfragment:
   a. **Zuerst suchen**: `kb_search`, ob eine Seite existiert.
   b. **Existiert sie**: mit neuen Infos aus dieser Quelle ergänzen, Quelle in Referenzen, `updated` setzen.
   c. **Neu**: im **richtigen Ordner** (siehe Tabelle) mit korrektem Frontmatter anlegen.
   d. **Eine Seite pro Entität** — niemals mehrere Firmen auf einer Seite.

5. **Quellenzusammenfassung** — Seite in `wiki/recherche/` mit:
   - Kernpunkten (Bullets)
   - Links zu allen aus dieser Quelle neu/aktualisierten Seiten
   - Original-URL und Erscheinungsdatum

6. **Synthese** (falls sinnvoll) — Bei Analyse oder Vergleich:
   - Seite in `wiki/ergebnisse/`, die Befunde bündelt
   - Verlinkung zu relevanten `akteure/`- und `wissen/`-Seiten

7. **Querverweise** — Für **jede** neu/aktualisierte Seite:
   - Abschnitt `## Verwandte Seiten` unten mit Links
   - Bidirektionale Links: verlinkt A auf B, muss B auch auf A verweisen
   - Quellenzusammenfassungen mit den daraus entstandenen Seiten verknüpfen

## Mindest-Checkliste

Nach einem Ingest musst du Seiten in **mindestens 2 verschiedenen Ordnern** angelegt/aktualisiert haben. Typisch:

- 1× `wiki/recherche/` (Quellenzusammenfassung) — **immer**
- 1–5× `wiki/akteure/` (pro erwähnter Firma/Person) — **falls vorhanden**
- 0–3× `wiki/wissen/` (Fakten, Trends, Markt, Regelung) — **nach Bedarf**
- 0–1× `wiki/ergebnisse/` (analytische Synthese) — **wenn die Quelle analytisch ist**

Wenn du nur `wiki/wissen/` befüllt hast, prüfe, ob Inhalte auch nach `recherche/` oder `akteure/` gehören.

## Fallstricke

- **`raw/`-Dateien nach dem Anlegen nicht ändern** — unveränderliches Archiv
- **Keine Riesenseiten** — fokussierte Einzelseiten
- **`wiki/akteure/` nicht auslassen** — jede genannte Firma/Person verdient eine Seite
- **`wiki/recherche/` nicht auslassen** — jede ingested Quelle braucht eine Zusammenfassungsseite
- **Nicht alles nach `wiki/ergebnisse/`** — dort nur fertige Analysen und Deliverables
- **Querverweise nicht vergessen** — verwaiste Seiten mindern die Qualität

## Verifikation

Vor „fertig“ alle Punkte prüfen:

1. Rohquelle in `raw/articles/` gespeichert (oder war schon da)
2. Quellenzusammenfassung in `wiki/recherche/` existiert
3. Entitätsseiten in `wiki/akteure/` für genannte Organisationen/Personen
4. Seiten in den **richtigen Ordnern** (nicht alles in `ergebnisse/`)
5. Korrektes Frontmatter (`title`, `category`, `tags`)
6. Querverweise — jede Seite hat „Verwandte Seiten“
7. Links bidirektional
8. Erst dann dem Nutzer Abschluss melden
