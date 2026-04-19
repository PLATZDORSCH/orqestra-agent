---
title: "Wiki Lint"
description: "Gesundheitscheck für das Wiki ausführen."
tags: [wiki, knowledge, maintenance]
version: 1
created: "2026-04-08"
---

# Wiki Lint

Führe einen Gesundheitscheck für das Wiki aus, um Probleme zu finden und die Qualität zu verbessern.

## Wann nutzen

- Nutzer wünscht Lint, Health-Check oder Qualitätsaudit
- Regelmäßig (z. B. wöchentlich)
- Nach einer großen Ingest-Serie

## Schritte

1. **Alle Wiki-Seiten lesen** — Mit `wiki/index.md` starten, dann referenzierte Seiten.

2. **Prüfungen durchführen:**

   **Widersprüche** — Aussagen, die sich zwischen Seiten widersprechen (Zahlen, Daten, Bewertungen).

   **Veraltete Inhalte** — Seiten mit altem `updated` oder veralteten Aussagen. `status: stale` im Frontmatter setzen.

   **Verwaiste Seiten** — Seiten ohne eingehende Links. Jede Seite sollte **mindestens 2** eingehende Links haben.

   **Fehlender Abschnitt „Verwandte Seiten“** — Seiten ohne diesen Abschnitt oder mit weniger als 2 Links darin.

   **Fehlende Bidirektionalität** — A verlinkt B, B verlinkt nicht zurück.

   **Fehlende Seiten** — Konzepte, Firmen oder Trends, die mehrfach erwähnt werden, aber keine eigene Seite haben.

   **Fehlende Querverweise** — thematisch verwandte Seiten ohne Link zueinander.

   **Datenlücken** — wichtige Themen nur mit einer oder keiner Quelle.

   **Index-Konsistenz** — Seiten existieren, fehlen im Index, oder Index zeigt auf nicht existierende Seiten.

   **Index-Aktualität** — Ist `wiki/index.md` aktuell (Katalog, Statistik)? Spiegelt es alle verarbeiteten Quellen?

3. **Bericht** — Ergebnisse nach Kategorie gruppiert präsentieren.

4. **Log-Eintrag** — An `wiki/log.md` anhängen (siehe englische Vorlage für Struktur).

5. **Fix-Vorschläge** — Konkrete Empfehlungen: fehlende Querverweise, neue Seiten, fehlende Quellen, Index-Update.

## Fallstricke

- Keine Änderungen ohne Zustimmung des Nutzers — nur berichten und vorschlagen
- Bei Widersprüchen beide Positionen zeigen, nicht einseitig entscheiden
- Log-Eintrag **nicht** vergessen

## Verifikation

Vor Abschluss: alle Bereiche geprüft, Bericht geliefert, `wiki/log.md` mit Lint-Eintrag.
