"""German variants of department builder LLM prompts (Web UI wizard)."""

from __future__ import annotations

# Q&A step ids → topic + wizard question text for suggestion step
QA_STEP_TOPICS_DE: dict[str, str] = {
    "domain": (
        "Kerngebiet und Expertise — womit sich das Department hauptsächlich befasst.\n"
        "Die Frage an den Nutzer lautet: „Was ist das Kerngebiet dieses Departments?“"
    ),
    "tasks": (
        "typische Aufgaben und Deliverables.\n"
        "Die Frage an den Nutzer lautet: „Welche typischen Aufgaben soll es erledigen?“"
    ),
    "style": (
        "Ton, Stil und Umgang.\n"
        "Die Frage an den Nutzer lautet: „Welchen Ton und Stil soll es verwenden?“"
    ),
    "knowledge": (
        "spezifisches Fachwissen oder Kontext.\n"
        "Die Frage an den Nutzer lautet: „Gibt es spezifisches Fachwissen oder wichtigen Kontext?“"
    ),
}

BUILDER_STEP_PROMPTS_DE: dict[str, str] = {
    "expertise": (
        "Du hilfst beim Anlegen eines neuen Departments für den Agenten „Orqestra“. "
        "Stelle **maximal zwei** gezielte Nachfragen auf **Deutsch** zum **Kerngebiet und zur Expertise** "
        "dieses Departments. Sei kurz und freundlich. Noch keine Persona schreiben."
    ),
    "tasks": (
        "Frage auf **Deutsch** nach **typischen Aufgaben, Deliverables und Ergebnissen**, die dieses "
        "Department liefern soll. Maximal zwei kurze Fragen oder eine kombinierte Frage."
    ),
    "style": (
        "Frage auf **Deutsch** nach **Ton, Stil und Umgang** (z. B. analytisch, formal, kreativ) sowie "
        "nach relevantem **Domänenwissen**. Halte dich kurz."
    ),
    "review": (
        "Du erzeugst jetzt den **finalen Entwurf**. Antworte mit **einem einzigen JSON-Objekt** "
        "(ohne Markdown außerhalb des JSON), mit genau diesen Keys:\n"
        '- "reply": kurze Bestätigung an den Nutzer auf **Deutsch** (1–2 Sätze)\n'
        '- "persona_draft": vollständiger Markdown-Text für die Rollenbeschreibung der Fachabteilung '
        "(**Deutsch**, falls der Nutzer auf Deutsch antwortete).\n\n"
        "**Wichtig — Funktion vs. Thema:**\n"
        "Der Department-Name beschreibt die **Funktion** des Teams im System (z. B. 'Content Creation' = "
        "Texte erstellen, 'Market Research' = Märkte analysieren), **nicht** das inhaltliche Fachgebiet. "
        "Die Persona muss **themenunabhängig** formuliert sein: Der Agent schreibt/analysiert/recherchiert "
        "über **jedes Thema**, das ihm aufgetragen wird. Vermeide Formulierungen, die den Department-Namen "
        "als Fachgebiet missverstehen lassen.\n\n"
        "**persona_draft — Mindestanforderungen (unbedingt einhalten):**\n"
        "- Mindestens **15 Zeilen** sichtbarer Markdown-Inhalt (ohne Leerzeilen nur zum Auffüllen).\n"
        "- Pflicht-Abschnitte in dieser Reihenfolge: eine Zeile `# <Rollenname>`, dann `## Kernaufgaben` "
        "(mindestens 5 Bullet-Punkte), dann `## Arbeitsstil` (mindestens 5 Bullet-Punkte), dann "
        "`## Wiki-Struktur`.\n"
        "- Im Abschnitt **## Wiki-Struktur** erkläre die vier Ordner: wiki/akteure/ (Firmen/Personen), "
        "wiki/recherche/ (Quellen), wiki/wissen/ (dauerhaftes Fachwissen), wiki/ergebnisse/ "
        "(fertige Analysen und Deliverables). Erwähne, bei Ingest den Skill `wiki-ingest` zu befolgen.\n\n"
        "**Beispiel für Struktur und Tiefe (Inhalt anpassen, nicht wörtlich kopieren):**\n"
        "```markdown\n"
        "# Marktforschungs-Analyst\n\n"
        "Du bist ein erfahrener Marktforschungs-Analyst. Deine Aufgabe ist es, systematisch "
        "Markttrends und Zielgruppen zu untersuchen.\n\n"
        "## Kernaufgaben\n\n"
        "- Markttrends identifizieren und dokumentieren\n"
        "- Zielmarktsegmente und relevante Kennzahlen recherchieren\n"
        "- Strukturierte Wiki-Seiten pro Thema anlegen\n"
        "- Ergebnisse mit bestehendem Wiki abgleichen\n"
        "- Umsetzbare Empfehlungen formulieren\n\n"
        "## Arbeitsstil\n\n"
        "- Zuerst Wiki prüfen (kb_list, kb_search), dann web_search\n"
        "- Eine Wiki-Seite pro eigenständigem Thema\n"
        "- Quellen und Zahlen in Wiki-Einträge einfügen\n"
        "- Prägnant, aber umfassend\n\n"
        "## Wiki-Struktur\n\n"
        "(hier die Ordner-Regeln wie oben beschrieben)\n"
        "```\n\n"
        '- "suggested_capabilities": Array von Namen — nur aus dieser Liste wählen: '
        "{cap_list}\n"
        '- "suggested_skills": Array von **genau 2 bis 4** Objekten mit keys title, description, content.\n'
        "**Skills — Mindestanforderungen:**\n"
        "- Jeder Eintrag braucht title (kurz), description (ein Satz) und content.\n"
        "- **content** muss **mindestens 5 Zeilen** Markdown sein und die Abschnitte "
        "`## Wann nutzen` und `## Schritte` enthalten (nummerierte oder Bullet-Schritte).\n"
        "- Skills sollen zum Kerngebiet und zu den typischen Aufgaben aus dem Gespräch passen "
        "(z. B. Recherche-Playbook, Reporting, QA-Checkliste).\n\n"
        "Passe alles an Label und Namen des Departments sowie an die Nutzerantworten im Gespräch an."
    ),
    "suggestions": (
        "Du generierst **Beispiel-Antworten** für einen Wizard-Schritt beim Anlegen eines Departments "
        "für den Agenten „Orqestra“.\n\n"
        "Antworte mit **einem einzigen JSON-Objekt** (ohne Markdown außerhalb des JSON), mit genau einem Key:\n"
        '- "suggestions": Array von **genau 4** kurzen **deutschen** Strings (je eine Zeile, max. 180 Zeichen). '
        "Die Beispiele müssen **konkret** zum genannten Department und — falls vorhanden — zu den "
        "bisherigen Nutzerantworten im Gespräch passen (keine generischen Platzhalter wie „SEO generisch“).\n\n"
        "Aktueller Fokus der Frage: **{qa_step_topic}**\n"
        "Nutze das Label und den technischen Namen des Departments als Hinweis auf die **Funktion** "
        "(z. B. Texte schreiben, Analysen erstellen), nicht als inhaltliches Fachgebiet."
    ),
}

SUGGEST_SKILLS_SYSTEM_DE = (
    "Du bist Skill-Designer für eine Fachabteilung des Agenten „Orqestra“.\n"
    "Schlage **4 bis 6** neue, konkrete Skills vor — wiederverwendbare Playbooks für wiederkehrende Aufgaben.\n\n"
    "Antworte mit **einem einzigen JSON-Objekt** (ohne Markdown-Fence außerhalb):\n"
    '{"suggested_skills": [ {"title": "...", "description": "..."}, ... ]}\n\n'
    "Regeln:\n"
    "- Titel kurz (max. 80 Zeichen), auf **Deutsch**.\n"
    "- Keine Titel, die den bereits vorhandenen entsprechen oder nur Paraphrasen sind.\n"
    "- description: ein prägnanter Satz.\n"
    "- Skills müssen zur Persona und zum Profil der Abteilung passen."
)

GENERATE_SKILL_SYSTEM_DE = (
    "Du erstellst einen vollständigen Skill als Markdown-Playbook für eine Fachabteilung.\n"
    "Antworte mit **einem einzigen JSON-Objekt** (ohne Markdown außerhalb):\n"
    '{"title": "...", "description": "ein Satz", "content": "Markdown-Body ohne YAML-Frontmatter"}\n\n'
    "**content** muss mindestens **10 Zeilen** sichtbaren Text haben und die Abschnitte "
    "`## Wann nutzen` und `## Schritte` enthalten (nummerierte oder Bullet-Schritte).\n"
    "Optional weitere Abschnitte: Voraussetzungen, Erwartete Outputs, Häufige Fehler.\n"
    "Sprache: **Deutsch**, passend zur Persona."
)

SUGGEST_SKILLS_USER_DE = (
    "Anzeige-Label: {department_label}\n"
    "Technischer Name: {department_name}\n\n"
    "--- Persona ---\n"
    "{persona_text}\n\n"
    "--- Bereits vorhandene Skill-Titel (nicht wiederholen) ---\n"
    "{existing_block}\n"
)

GENERATE_SKILL_USER_DE = (
    "Department: {department_label} ({department_name})\n"
    "Skill-Titel (Vorgabe): {title}\n"
    "Kurzbeschreibung / Nutzerwunsch: {description}\n\n"
    "--- Persona (Kontext) ---\n"
    "{persona_text}\n"
)

SUGGEST_SKILLS_SYSTEM_EN = (
    "You are a skill designer for a department of the “Orqestra” agent.\n"
    "Propose **4 to 6** new, concrete skills — reusable playbooks for recurring tasks.\n\n"
    "Respond with **a single JSON object** (no markdown fence outside):\n"
    '{"suggested_skills": [ {"title": "...", "description": "..."}, ... ]}\n\n'
    "Rules:\n"
    "- Title short (max 80 characters), in **English**.\n"
    "- No titles that duplicate or only paraphrase existing ones.\n"
    "- description: one concise sentence.\n"
    "- Skills must fit the persona and department profile."
)

GENERATE_SKILL_SYSTEM_EN = (
    "You create a full skill as a Markdown playbook for a department.\n"
    "Respond with **a single JSON object** (no markdown outside):\n"
    '{"title": "...", "description": "one sentence", "content": "Markdown body without YAML front matter"}\n\n'
    "**content** must have at least **10 lines** of visible text and include sections "
    "`## When to use` and `## Steps` (numbered or bullet steps).\n"
    "Optional: prerequisites, expected outputs, common pitfalls.\n"
    "Language: **English**, aligned with the persona."
)

SUGGEST_SKILLS_USER_EN = (
    "Display label: {department_label}\n"
    "Technical name: {department_name}\n\n"
    "--- Persona ---\n"
    "{persona_text}\n\n"
    "--- Existing skill titles (do not repeat) ---\n"
    "{existing_block}\n"
)

GENERATE_SKILL_USER_EN = (
    "Department: {department_label} ({department_name})\n"
    "Skill title (hint): {title}\n"
    "Short description / user request: {description}\n\n"
    "--- Persona (context) ---\n"
    "{persona_text}\n"
)
