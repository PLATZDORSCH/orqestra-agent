---
title: "Wiki Delete"
description: "Wiki-Seiten sauber löschen — entfernt die Datei und bereinigt Querverweise automatisch."
tags: [wiki, knowledge-management]
version: 1
created: "2026-04-10"
---

# Wiki Delete

Lösche eine oder mehrere Wiki-Seiten. Das System bereinigt automatisch alle Querverweise.

## Wann nutzen

- Nutzer möchte bestimmte Wiki-Seiten entfernen oder aufräumen
- Veraltete oder falsche Seiten müssen weg
- Duplikate zusammenführen (Duplikat löschen, Original behalten)

## Was das System automatisch erledigt

Bei `kb_delete`:

1. Datei wird von der Festplatte entfernt
2. **Alle** anderen Wiki-Seiten werden auf Links zur gelöschten Seite gescannt und bereinigt
3. `sources`- und `references`-Arrays im Frontmatter referenzierender Seiten werden bereinigt
4. `wiki/index.md` wird neu aufgebaut (Katalog und Statistik)
5. Die Löschung wird in `wiki/log.md` protokolliert

Du **musst** Verweise **nicht** manuell bereinigen — `kb_delete` übernimmt das.

## Schritte

1. **Mit Nutzer abklären** — Vor dem Löschen Titel und Pfad zeigen. Bei unklarer Zielseite nachfragen.

2. **Referenzen prüfen** — `kb_related`, um zu sehen, welche Seiten verlinken. Mitteilen, wie viele Seiten bereinigt werden.

3. **Löschen** — `kb_delete` mit dem Seitenpfad aufrufen. Antwort prüfen, welche Seiten bereinigt wurden.

4. **Verifizieren** — `kb_search`, ob die Seite nicht mehr auftaucht.

5. **Bericht** — Dem Nutzer mitteilen:
   - welche Seite gelöscht wurde
   - wie viele Seiten Referenzen verloren haben
   - Namen der bereinigten Seiten

## Geschützte Seiten

Diese Seiten **dürfen nicht** gelöscht werden:
- `wiki/index.md` — auto-generierter Katalog
- `wiki/log.md` — Operationslog
- `wiki/memory.md` — Agenten-Gedächtnis

## Massen-Löschung

Mehrere Seiten nacheinander verarbeiten; `wiki/index.md` wird am Ende automatisch neu aufgebaut.

## Fallstricke

- **`raw/`-Dateien nicht löschen**, außer der Nutzer verlangt es ausdrücklich — Rohquellen sind das Archiv
- **Nicht ohne Bestätigung löschen**, wenn eine Seite viele eingehende Links hat
