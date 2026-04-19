---
title: "Wiki Newsletter"
description: "Wöchentliche Zusammenfassung aus aktueller Wiki-Aktivität."
tags: [wiki, content, newsletter]
version: 1
created: "2026-04-08"
---

# Wiki Newsletter

Erstelle eine wöchentliche Review aus der aktuellen Wiki-Aktivität.

## Wann nutzen

- Nutzer möchte Newsletter oder Weekly Review
- Wöchentlich (z. B. per Cron)
- Formulierungen wie „was war diese Woche“, „Weekly Update“ usw.

## Schritte

1. **Log scannen** — `wiki/log.md` lesen, Einträge der letzten 7 Tage.

2. **Neue und aktualisierte Seiten** — Alle Seiten mit `updated` in den letzten 7 Tagen; besonders `wiki/wissen/` für Trendänderungen.

3. **Vorlage** — Optional früheren Newsletter in `wiki/ergebnisse/` als Stilreferenz.

4. **Newsletter schreiben** — In `wiki/ergebnisse/` als `YYYY-MM-DD-newsletter-cwXX.md`:
   - 3–5 Top-Themen der Woche mit Kontext
   - Trend-Tabelle (was steigt, was fällt)
   - 1–2 „auf dem Radar“-Themen (schwache Signale)
   - Metadaten: `title`, `format: newsletter`, `based_on`, `created`, `status: draft`

5. **Log-Eintrag** — An `wiki/log.md` anhängen (Zeitraum, Anzahl Quellen, gespeicherte Datei).

## Fallstricke

- Nur Fakten aus dem Wiki, nichts erfinden
- Bei wenig Aktivität: kurze Notiz statt leerem Newsletter
- Kontext und Analyse, nicht nur Listen
- Log-Eintrag nicht vergessen

## Verifikation

Newsletter-Entwurf in `wiki/ergebnisse/`, Daten aus echten Wiki-Seiten, `wiki/log.md` mit Eintrag.
