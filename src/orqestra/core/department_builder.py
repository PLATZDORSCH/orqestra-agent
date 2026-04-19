"""Shared department builder wizard (Web API, CLI `/department`, Telegram `/department`)."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import frontmatter

from orqestra._paths import REPO_ROOT
from orqestra.core.bootstrap import resolve_env
from orqestra.core.llm_text import strip_think_tags
from orqestra.core.departments import (
    SHARED_CAPS,
    DepartmentRegistry,
    available_shared_capability_names,
    load_departments_yaml,
    save_departments_yaml,
    sync_orchestrator_department_tools,
    update_orchestrator_persona_file,
)
from orqestra.core.engine import StrategyEngine
from orqestra.core.localization import normalize_language, pick_localized_markdown
from orqestra.core.registry import DEFAULT_DEPT_COLORS
from orqestra.core.department_builder_prompts_de import (
    BUILDER_STEP_PROMPTS_DE,
    GENERATE_SKILL_SYSTEM_DE,
    GENERATE_SKILL_SYSTEM_EN,
    GENERATE_SKILL_USER_DE,
    GENERATE_SKILL_USER_EN,
    QA_STEP_TOPICS_DE,
    SUGGEST_SKILLS_SYSTEM_DE,
    SUGGEST_SKILLS_SYSTEM_EN,
    SUGGEST_SKILLS_USER_DE,
    SUGGEST_SKILLS_USER_EN,
)

log = logging.getLogger(__name__)



def parse_json_object(text: str) -> dict[str, Any]:
    text = strip_think_tags(text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    i = text.find("{")
    if i >= 0:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[i:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    raise ValueError("No valid JSON in model response")


def slugify_skill_name(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return (s.strip("-") or "skill")[:80]


# Web UI Q&A step ids → topic + exact wizard question for LLM suggestion prompts
QA_STEP_TOPICS_EN: dict[str, str] = {
    "domain": (
        "Core domain and expertise — what this department mainly does.\n"
        "The user-facing question is: “What is this department’s core domain?”"
    ),
    "tasks": (
        "typical tasks and deliverables.\n"
        "The user-facing question is: “What typical tasks should it handle?”"
    ),
    "style": (
        "tone, style, and manner.\n"
        "The user-facing question is: “What tone and style should it use?”"
    ),
    "knowledge": (
        "specific domain knowledge or context.\n"
        "The user-facing question is: “Is there specific domain knowledge or important context?”"
    ),
}


def slugify_label(label: str) -> str:
    """Match web `slugifyLabel` (DepartmentBuilder.tsx)."""
    s = label.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"^-+|-+$", "", s)
    s = s[:48]
    if not s:
        return ""
    if not re.match(r"^[a-z]", s):
        s = "d-" + s
    s = re.sub(r"[^a-z0-9_-]", "-", s)
    return s[:64]


BUILDER_STEP_PROMPTS_EN: dict[str, str] = {
    "expertise": (
        "You help create a new department for the “Orqestra” agent. "
        "Ask **at most two** focused follow-up questions in **English** about the **core domain and expertise** "
        "of this department. Be brief and friendly. Do not write the persona yet."
    ),
    "tasks": (
        "Ask in **English** about **typical tasks, deliverables, and outputs** this "
        "department should produce. At most two short questions or one combined question."
    ),
    "style": (
        "Ask in **English** about **tone, style, and manner** (e.g. analytical, formal, creative) and "
        "relevant **domain knowledge**. Keep it short."
    ),
    "review": (
        "You now produce the **final draft**. Respond with **a single JSON object** "
        "(no markdown outside the JSON), with exactly these keys:\n"
        '- "reply": short confirmation to the user in English (1–2 sentences)\n'
        '- "persona_draft": full Markdown for the department role description '
        "(prefer English if the user wrote in English; otherwise match the user’s language).\n\n"
        "**Important — function vs. topic:**\n"
        "The department name describes the team’s **function** in the system (e.g. 'Content Creation' = "
        "writing text, 'Market Research' = analyzing markets), **not** the subject domain. "
        "The persona must be **topic-agnostic**: the agent writes/analyzes/researches "
        "**any topic** it is assigned. Avoid wording that misreads the department name as a subject domain.\n\n"
        "**persona_draft — minimum requirements (must follow):**\n"
        "- At least **15 lines** of visible Markdown (not padded with blank lines only).\n"
        "- Required sections in this order: one line `# <Role name>`, then `## Core responsibilities` "
        "(at least 5 bullets), then `## Working style` (at least 5 bullets), then "
        "`## Wiki structure`.\n"
        "- In **## Wiki structure** explain the four folders: wiki/akteure/ (companies/people), "
        "wiki/recherche/ (sources), wiki/wissen/ (durable knowledge), wiki/ergebnisse/ "
        "(finished analyses and deliverables). Mention following the `wiki-ingest` skill on ingest.\n\n"
        "**Example structure and depth (adapt content, do not copy verbatim):**\n"
        "```markdown\n"
        "# Market research analyst\n\n"
        "You are an experienced market research analyst. Your job is to systematically "
        "investigate market trends and target segments.\n\n"
        "## Core responsibilities\n\n"
        "- Identify and document market trends\n"
        "- Research target segments and relevant metrics\n"
        "- Create structured wiki pages per topic\n"
        "- Align results with existing wiki content\n"
        "- Formulate actionable recommendations\n\n"
        "## Working style\n\n"
        "- Check wiki first (kb_list, kb_search), then web_search\n"
        "- One wiki page per distinct topic\n"
        "- Include sources and numbers in wiki entries\n"
        "- Concise but thorough\n\n"
        "## Wiki structure\n\n"
        "(folder rules as described above)\n"
        "```\n\n"
        '- "suggested_capabilities": array of names — choose only from this list: '
        "{cap_list}\n"
        '- "suggested_skills": array of **exactly 2 to 4** objects with keys title, description, content.\n'
        "**Skills — minimum requirements:**\n"
        "- Each entry needs title (short), description (one sentence), and content.\n"
        "- **content** must be **at least 5 lines** of Markdown and include sections "
        "`## When to use` and `## Steps` (numbered or bullet steps).\n"
        "- Skills should fit the core domain and typical tasks from the conversation "
        "(e.g. research playbook, reporting, QA checklist).\n\n"
        "Align everything with the department label and name and the user’s answers in the conversation."
    ),
    "suggestions": (
        "You generate **example answers** for a wizard step when creating a department "
        "for the “Orqestra” agent.\n\n"
        "Respond with **a single JSON object** (no markdown outside the JSON), with exactly one key:\n"
        '- "suggestions": array of **exactly 4** short strings in **English** (one line each, max 180 chars). '
        "Examples must be **concrete** for the named department and — if present — prior "
        "user answers in the conversation (no generic placeholders like “generic SEO”).\n\n"
        "Current focus of the question: **{qa_step_topic}**\n"
        "Use the label and technical name of the department as hints for **function** "
        "(e.g. writing text, producing analyses), not as the subject domain."
    ),
}


def _builder_prompts(lang: str | None) -> dict[str, str]:
    return BUILDER_STEP_PROMPTS_DE if normalize_language(lang) == "de" else BUILDER_STEP_PROMPTS_EN


def _qa_topics(lang: str | None) -> dict[str, str]:
    return QA_STEP_TOPICS_DE if normalize_language(lang) == "de" else QA_STEP_TOPICS_EN


def run_builder_chat_llm(
    engine: StrategyEngine,
    *,
    step: str,
    messages: list[dict[str, Any]],
    department_name: str | None = None,
    department_label: str | None = None,
    qa_step: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """Run one builder step; returns same shape as HTTP builder_chat."""
    prompts = _builder_prompts(language)
    if step not in prompts:
        raise ValueError(f"Unknown step: {step}")

    cap_list = ", ".join(available_shared_capability_names())
    qa_topic = ""  # filled for step == "suggestions"; used in synthetic user message
    de = normalize_language(language) == "de"
    ctx_line = (
        "\n(Der Department-Name beschreibt die Funktion, nicht das Fachgebiet.)\n"
        if de
        else "\n(The department name describes function, not subject domain.)\n"
    )
    if step == "review":
        system = prompts["review"].format(cap_list=cap_list)
        ctx = ctx_line
        if department_name:
            ctx += f"{'Department-Name (technisch)' if de else 'Department name (technical)'}: {department_name}\n"
        if department_label:
            ctx += f"{'Anzeige-Label' if de else 'Display label'}: {department_label}\n"
        system = ctx + system
    elif step == "suggestions":
        topics = _qa_topics(language)
        topic_key = qa_step if qa_step in topics else "domain"
        qa_topic = topics[topic_key]
        system = prompts["suggestions"].format(qa_step_topic=qa_topic)
        ctx = ctx_line
        if department_name:
            ctx += f"{'Department-Name (technisch)' if de else 'Department name (technical)'}: {department_name}\n"
        if department_label:
            ctx += f"{'Anzeige-Label' if de else 'Display label'}: {department_label}\n"
        system = ctx + system
    else:
        system = prompts[step]
        if department_name or department_label:
            system += (
                "\n\nKontext (der Name beschreibt die Funktion im System, nicht das Fachgebiet):\n"
                if de
                else "\n\nContext (the name describes function in the system, not subject domain):\n"
            )
            if department_label:
                system += f"- Label: {department_label}\n"
            if department_name:
                system += f"- Name: {department_name}\n"

    msgs: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": str(content)})

    if step == "suggestions" and len(msgs) == 1:
        label_str = department_label or department_name or "Department"
        topic_line = qa_topic or _qa_topics(language)["domain"]
        if de:
            user_sug = (
                f'Generiere 4 passende Beispiel-Antworten für das Department "{label_str}".\n'
                f"Die Frage, auf die sich die Vorschläge beziehen:\n{topic_line}"
            )
        else:
            user_sug = (
                f'Generate 4 suitable example answers for the department "{label_str}".\n'
                f"The question the suggestions refer to:\n{topic_line}"
            )
        msgs.append({"role": "user", "content": user_sug})

    temp = 0.7 if step in ("review", "suggestions") else 0.6
    resp = engine.llm.chat.completions.create(
        model=engine.model,
        messages=msgs,
        temperature=temp,
    )
    raw = (resp.choices[0].message.content or "").strip()
    if step == "suggestions":
        log.debug("builder suggestions raw (%d chars): %s", len(raw), raw[:300])
        try:
            data = parse_json_object(raw)
        except ValueError:
            log.warning("builder suggestions did not return JSON: %s", raw[:500])
            return {"reply": "", "suggestions": []}
        sug = data.get("suggestions")
        if not isinstance(sug, list):
            return {"reply": "", "suggestions": []}
        out: list[str] = []
        for x in sug:
            if isinstance(x, (str, int, float)):
                s = str(x).strip()
                if s:
                    out.append(s[:200])
            if len(out) >= 4:
                break
        return {"reply": "", "suggestions": out}

    if step != "review":
        return {"reply": raw}

    try:
        data = parse_json_object(raw)
    except ValueError as exc:
        log.warning("builder review did not return JSON: %s", raw[:500])
        raise ValueError("Model did not return valid JSON for the review step.") from exc

    reply = data.get("reply", "")
    return {
        "reply": reply if isinstance(reply, str) else str(reply),
        "persona_draft": data.get("persona_draft"),
        "suggested_capabilities": data.get("suggested_capabilities"),
        "suggested_skills": data.get("suggested_skills"),
    }


@dataclass
class SkillDraft:
    title: str
    description: str = ""
    content: str = ""


def fallback_starter_skills(language: str | None = None) -> list[SkillDraft]:
    """Generic starter skills when LLM suggestion/generation fails (no department name in titles)."""
    de = normalize_language(language) == "de"
    if de:
        return [
            SkillDraft(
                title="Einstieg",
                description="Standardvorgehen für den ersten Auftrag in diesem Department",
                content=(
                    "## Wann nutzen\n\n"
                    "- Wenn eine neue Aufgabe in diesem Bereich startet\n"
                    "- Wenn noch kein passendes Playbook im Wiki existiert\n\n"
                    "## Schritte\n\n"
                    "1. Kontext und Ziel mit dem Nutzer oder der Aufgabenbeschreibung klären\n"
                    "2. Wiki auf vorhandene Informationen prüfen (kb_search, kb_list)\n"
                    "3. Recherche oder Analyse mit den passenden Tools durchführen\n"
                    "4. Ergebnisse strukturiert aufbereiten und Quellen angeben\n"
                    "5. Im passenden Wiki-Ordner speichern und Verknüpfungen setzen\n"
                ),
            ),
            SkillDraft(
                title="Wiki-Dokumentation",
                description="Kurz-Checkliste für saubere Wiki-Einträge",
                content=(
                    "## Wann nutzen\n\n"
                    "- Vor dem Speichern einer neuen oder überarbeiteten Wiki-Seite\n"
                    "- Wenn mehrere Quellen zu einem Thema zusammenkommen\n\n"
                    "## Schritte\n\n"
                    "1. Einen klaren Seitentitel und genau einen Hauptfokus wählen\n"
                    "2. Ordner wählen (akteure, recherche, wissen, ergebnisse — siehe Persona)\n"
                    "3. Metadaten und ggf. Tags setzen; Duplikate vermeiden\n"
                    "4. Kurze Zusammenfassung oben, Details und Quellen unten\n"
                ),
            ),
        ]
    return [
        SkillDraft(
            title="Getting started",
            description="Default procedure for the first task in this department",
            content=(
                "## When to use\n\n"
                "- When a new task in this area begins\n"
                "- When no matching playbook exists in the wiki yet\n\n"
                "## Steps\n\n"
                "1. Clarify context and goal with the user or task description\n"
                "2. Check the wiki for existing information (kb_search, kb_list)\n"
                "3. Run research or analysis with the appropriate tools\n"
                "4. Prepare results in a structured way and cite sources\n"
                "5. Save into the matching wiki folder and add links\n"
            ),
        ),
        SkillDraft(
            title="Wiki documentation",
            description="Short checklist for clean wiki entries",
            content=(
                "## When to use\n\n"
                "- Before saving a new or revised wiki page\n"
                "- When multiple sources converge on a topic\n\n"
                "## Steps\n\n"
                "1. Pick a clear page title with exactly one main focus\n"
                "2. Choose the folder (akteure, recherche, wissen, ergebnisse — see persona)\n"
                "3. Set metadata and tags; avoid duplicates\n"
                "4. Short summary on top, details and sources below\n"
            ),
        ),
    ]


def save_skill_draft_to_directory(
    skills_dir: Path,
    dept_name: str,
    sk: SkillDraft,
    *,
    tags: list[str] | None = None,
) -> str:
    """Write one skill ``.md`` under ``skills_dir``. Returns basename (e.g. ``foo.md``)."""
    skills_dir.mkdir(parents=True, exist_ok=True)
    stem = slugify_skill_name(sk.title)
    fn = f"{stem}.md"
    p = skills_dir / fn
    if p.exists():
        stem = stem + "-skill"
        fn = f"{stem}.md"
        p = skills_dir / fn
    tag_list = tags if tags is not None else ["starter", dept_name]
    meta: dict[str, Any] = {
        "title": sk.title,
        "description": (sk.description or "")[:500],
        "tags": tag_list,
        "version": 1,
        "created": str(date.today()),
    }
    post = frontmatter.Post(sk.content or f"# {sk.title}\n", **meta)
    p.write_text(frontmatter.dumps(post), encoding="utf-8")
    return fn


def suggest_skills_for_department(
    engine: StrategyEngine,
    *,
    persona_text: str,
    department_label: str,
    department_name: str,
    existing_skill_titles: list[str],
    language: str | None = None,
) -> list[dict[str, str]]:
    """LLM: 4–6 short skill ideas (title + description) for the Skill Builder wizard."""
    existing_block = "\n".join(f"- {t}" for t in existing_skill_titles) or (
        "(keine)" if normalize_language(language) == "de" else "(none)"
    )
    de = normalize_language(language) == "de"
    system = SUGGEST_SKILLS_SYSTEM_DE if de else SUGGEST_SKILLS_SYSTEM_EN
    user = (SUGGEST_SKILLS_USER_DE if de else SUGGEST_SKILLS_USER_EN).format(
        department_label=department_label,
        department_name=department_name,
        persona_text=persona_text[:12000],
        existing_block=existing_block,
    )
    resp = engine.llm.chat.completions.create(
        model=engine.model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
    )
    raw = (resp.choices[0].message.content or "").strip()
    data = parse_json_object(raw)
    items = data.get("suggested_skills")
    if not isinstance(items, list):
        return []
    out: list[dict[str, str]] = []
    for x in items:
        if not isinstance(x, dict):
            continue
        t = x.get("title")
        d = x.get("description", "")
        if isinstance(t, str) and t.strip():
            out.append({"title": t.strip()[:200], "description": str(d).strip()[:500] if d else ""})
        if len(out) >= 6:
            break
    return out


def generate_skill_content(
    engine: StrategyEngine,
    *,
    persona_text: str,
    department_label: str,
    department_name: str,
    title: str,
    description: str,
    language: str | None = None,
) -> SkillDraft:
    """LLM: full skill body (Markdown) for one chosen or custom skill."""
    de = normalize_language(language) == "de"
    system = GENERATE_SKILL_SYSTEM_DE if de else GENERATE_SKILL_SYSTEM_EN
    desc_fallback = (
        "(keine weitere Beschreibung)" if de else "(no further description)"
    )
    user = (GENERATE_SKILL_USER_DE if de else GENERATE_SKILL_USER_EN).format(
        department_label=department_label,
        department_name=department_name,
        title=title,
        description=description or desc_fallback,
        persona_text=persona_text[:12000],
    )
    resp = engine.llm.chat.completions.create(
        model=engine.model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.5,
    )
    raw = (resp.choices[0].message.content or "").strip()
    data = parse_json_object(raw)
    out_title = data.get("title") if isinstance(data.get("title"), str) else title
    out_desc = data.get("description") if isinstance(data.get("description"), str) else description
    out_content = data.get("content") if isinstance(data.get("content"), str) else ""
    if not str(out_title).strip():
        out_title = title
    return SkillDraft(
        title=str(out_title).strip()[:200],
        description=str(out_desc or "").strip()[:500],
        content=str(out_content or "").strip(),
    )


# ── Template installer ────────────────────────────────────────────────

_TEMPLATES_DIR = REPO_ROOT / "templates"


def list_templates() -> list[dict[str, Any]]:
    """Return available department templates from the templates/ directory."""
    if not _TEMPLATES_DIR.is_dir():
        return []
    results = []
    for d in sorted(_TEMPLATES_DIR.iterdir()):
        cfg_path = d / "template.yaml"
        if not cfg_path.is_file():
            continue
        import yaml
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        results.append({
            "name": cfg.get("name", d.name),
            "label": cfg.get("label", d.name.title()),
            "label_de": cfg.get("label_de", ""),
            "description": cfg.get("description", ""),
            "description_de": cfg.get("description_de", ""),
            "capabilities": cfg.get("capabilities", []),
            "path": str(d),
        })
    return results


def install_template(
    template_name: str,
    *,
    root: Path,
    registry: DepartmentRegistry,
    engine: StrategyEngine,
    cfg: dict,
    language: str | None = None,
) -> dict[str, Any]:
    """Install a department from a template. Returns result dict."""
    tpl_dir = _TEMPLATES_DIR / template_name
    cfg_path = tpl_dir / "template.yaml"
    if not cfg_path.is_file():
        raise ValueError(f"Template not found: {template_name}")

    import yaml
    with open(cfg_path, encoding="utf-8") as f:
        tpl = yaml.safe_load(f) or {}

    name = tpl.get("name", template_name)
    label = tpl.get("label", name.title())
    capabilities = tpl.get("capabilities", [])

    # Choose persona based on language
    is_german = language and language.lower().startswith("de")
    persona_file = "persona.de.md" if is_german and (tpl_dir / "persona.de.md").exists() else "persona.md"
    persona_path = tpl_dir / persona_file
    if not persona_path.exists():
        raise ValueError(f"Template persona not found: {persona_path}")
    persona_content = persona_path.read_text(encoding="utf-8")

    if is_german:
        label = tpl.get("label_de") or label

    # Load skills
    skills: list[SkillDraft] = []
    skills_dir = tpl_dir / "skills"
    if skills_dir.is_dir():
        seen: set[str] = set()
        for sk_file in sorted(skills_dir.glob("*.md")):
            if sk_file.name.endswith(".de.md"):
                continue
            try:
                resolved = pick_localized_markdown(sk_file, language)
                stem_key = sk_file.stem
                if stem_key in seen:
                    continue
                seen.add(stem_key)
                doc = frontmatter.load(str(resolved))
                skills.append(SkillDraft(
                    title=doc.metadata.get("title", resolved.stem),
                    description=doc.metadata.get("description", ""),
                    content=doc.content or "",
                ))
            except Exception:
                log.warning("Skipping invalid skill template: %s", sk_file)

    return create_department_from_builder(
        root=root,
        registry=registry,
        engine=engine,
        cfg=cfg,
        name=name,
        label=label,
        persona_content=persona_content,
        capabilities=capabilities,
        skills=skills,
    )


def create_department_from_builder(
    *,
    root: Path,
    registry: DepartmentRegistry,
    engine: StrategyEngine,
    cfg: dict,
    name: str,
    label: str,
    persona_content: str,
    capabilities: list[str],
    skills: list[SkillDraft],
) -> dict[str, Any]:
    """Create department on disk and register it. Raises ValueError on validation errors."""
    name = name.strip().lower()
    if not re.match(r"^[a-z][a-z0-9_-]{0,63}$", name):
        raise ValueError(
            "Invalid name: only lowercase letters, digits, _ and - (must start with a letter)."
        )

    if registry.get(name):
        raise ValueError(f"Department already exists: {name}")

    shared_caps = [
        cap for cap in capabilities
        if not cap.startswith(("kb_", "skill_"))
    ]
    for cap in shared_caps:
        if cap not in SHARED_CAPS:
            raise ValueError(f"Unknown capability: {cap}")

    dept_dir = root / "departments" / name
    persona_path = dept_dir / "persona.md"
    kb_rel = f"departments/{name}/knowledge_base"
    skills_rel = f"departments/{name}/skills"
    skills_dir = root / skills_rel

    dept_dir.mkdir(parents=True, exist_ok=True)
    persona_path.write_text(persona_content.strip() + "\n", encoding="utf-8")
    skills_dir.mkdir(parents=True, exist_ok=True)

    for sk in skills:
        save_skill_draft_to_directory(skills_dir, name, sk, tags=["starter", name])

    from orqestra.capabilities.knowledge import KnowledgeBase

    KnowledgeBase(root / kb_rel)

    rows = load_departments_yaml(root)
    dept_cfg = {
        "name": name,
        "label": label.strip() or name.title(),
        "color": DEFAULT_DEPT_COLORS[len(rows) % len(DEFAULT_DEPT_COLORS)],
        "persona": f"departments/{name}/persona.md",
        "knowledge_base": kb_rel,
        "skills": skills_rel,
        "capabilities": shared_caps,
    }
    if any(r.get("name") == name for r in rows):
        raise ValueError(f"Department already in departments.yaml: {name}")
    rows.append(dept_cfg)
    save_departments_yaml(root, rows)

    engine_cfg = cfg.get("engine") or {}
    llm_cfg = cfg.get("llm") or {}
    base_url = resolve_env(llm_cfg.get("base_url", "https://api.openai.com/v1"))
    api_key = resolve_env(llm_cfg.get("api_key", "${OPENAI_API_KEY}"))
    model = llm_cfg.get("model", "gpt-4o")

    registry.add_department(
        dept_cfg,
        root=root,
        llm_base_url=base_url,
        llm_api_key=api_key,
        llm_model=model,
        language=engine_cfg.get("language"),
        context_window=int(engine_cfg.get("context_window", 0)),
        summarize_at=float(engine_cfg.get("summarize_at", 0.7)),
    )

    update_orchestrator_persona_file(registry, root)
    sync_orchestrator_department_tools(engine, registry)
    engine.invalidate_persona()

    dept = registry.get(name)
    assert dept is not None
    return {
        "name": name,
        "label": dept.label,
        "capabilities": dept.engine.capabilities.names(),
        "skills": dept.skills_summary(),
    }


@dataclass
class BuilderResponse:
    text: str
    phase: str
    done: bool = False
    created_department: str | None = None


@dataclass
class DepartmentBuilderSession:
    """Conversational wizard: name → expertise → tasks → style → review → confirm."""

    engine: StrategyEngine
    registry: DepartmentRegistry
    cfg: dict
    root: Path
    phase: str = "name"
    label: str = ""
    dept_name: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    persona_draft: str = ""
    suggested_capabilities: list[str] = field(default_factory=list)
    suggested_skills: list[SkillDraft] = field(default_factory=list)

    def start(self) -> BuilderResponse:
        return BuilderResponse(
            text=(
                "**Department generator**\n\n"
                "Enter the **display name** (e.g. *Market analysis*).\n"
                "Optionally on the same line the **technical name** (only a–z, 0–9, `_`, `-`): "
                "`Market analysis market-analysis`\n\n"
                "Type `/cancel` to abort."
            ),
            phase="name",
        )

    def advance(self, user_input: str) -> BuilderResponse:
        raw = user_input.strip()
        low = raw.lower()

        if low in ("/cancel", "abbrechen", "cancel"):
            self.phase = "done"
            return BuilderResponse(
                text="Department generator cancelled.",
                phase="done",
                done=True,
            )

        if self.phase == "name":
            return self._handle_name(raw)

        if self.phase == "expertise":
            return self._after_user_step(raw, "expertise", "tasks")

        if self.phase == "tasks":
            return self._after_user_step(raw, "tasks", "style")

        if self.phase == "style":
            return self._after_style(raw)

        if self.phase == "confirm":
            return self._handle_confirm(raw)

        self.phase = "done"
        return BuilderResponse(text="Done.", phase="done", done=True)

    def _handle_name(self, raw: str) -> BuilderResponse:
        parts = raw.strip().split()
        if not parts:
            return BuilderResponse(
                text="Please enter a display name (or `/cancel`).",
                phase="name",
            )
        last = parts[-1].lower()
        if len(parts) >= 2 and re.match(r"^[a-z][a-z0-9_-]{0,63}$", last):
            label_part = " ".join(parts[:-1]).strip()
            name_part = last
        else:
            label_part = raw.strip()
            name_part = slugify_label(label_part)

        if not label_part:
            return BuilderResponse(
                text="Please enter a display name (or `/cancel`).",
                phase="name",
            )

        if not name_part or not re.match(r"^[a-z][a-z0-9_-]{0,63}$", name_part):
            return BuilderResponse(
                text=(
                    "Invalid technical name. Only lowercase letters, digits, `_`, `-`, "
                    "starting with a letter. Example: `market-analysis` or two parts: "
                    "`My label my-label`"
                ),
                phase="name",
            )

        if self.registry.get(name_part):
            return BuilderResponse(
                text=f"Department **{name_part}** already exists. Choose another name.",
                phase="name",
            )

        self.label = label_part
        self.dept_name = name_part
        self.phase = "expertise"
        self.messages = []

        try:
            out = run_builder_chat_llm(
                self.engine,
                step="expertise",
                messages=self.messages,
                department_name=self.dept_name,
                department_label=self.label,
            )
        except Exception as exc:
            log.exception("builder expertise failed")
            self.phase = "done"
            return BuilderResponse(
                text=f"Error calling model: {exc}",
                phase="done",
                done=True,
            )

        reply = out.get("reply", "")
        self.messages.append({"role": "assistant", "content": reply})
        return BuilderResponse(
            text=f"{reply}\n\n*(Reply below; `/cancel` to abort.)*",
            phase="expertise",
        )

    def _after_user_step(self, raw: str, current: str, next_step: str) -> BuilderResponse:
        if not raw:
            return BuilderResponse(
                text="Please enter a reply (or `/cancel`).",
                phase=current,
            )
        self.messages.append({"role": "user", "content": raw})

        try:
            out = run_builder_chat_llm(
                self.engine,
                step=next_step,
                messages=self.messages,
                department_name=self.dept_name,
                department_label=self.label,
            )
        except Exception as exc:
            log.exception("builder step %s failed", next_step)
            self.phase = "done"
            return BuilderResponse(
                text=f"Error calling model: {exc}",
                phase="done",
                done=True,
            )

        reply = out.get("reply", "")
        self.messages.append({"role": "assistant", "content": reply})
        self.phase = next_step
        return BuilderResponse(
            text=f"{reply}\n\n*(Reply below; `/cancel` to abort.)*",
            phase=next_step,
        )

    def _after_style(self, raw: str) -> BuilderResponse:
        if not raw:
            return BuilderResponse(
                text="Please enter a reply (or `/cancel`).",
                phase="style",
            )
        self.messages.append({"role": "user", "content": raw})

        try:
            out = run_builder_chat_llm(
                self.engine,
                step="review",
                messages=self.messages,
                department_name=self.dept_name,
                department_label=self.label,
            )
        except ValueError as exc:
            self.phase = "done"
            return BuilderResponse(
                text=str(exc),
                phase="done",
                done=True,
            )
        except Exception as exc:
            log.exception("builder review failed")
            self.phase = "done"
            return BuilderResponse(
                text=f"Error calling model: {exc}",
                phase="done",
                done=True,
            )

        reply = out.get("reply", "")
        pd = out.get("persona_draft")
        if isinstance(pd, str) and pd.strip():
            self.persona_draft = pd.strip()
        else:
            lbl = self.label
            self.persona_draft = (
                f"# {lbl}\n\n"
                f"You are the **{lbl}** specialist. Deliver precise, traceable results "
                "and document them in the department wiki.\n\n"
                "## Core responsibilities\n\n"
                "- Execute tasks from the user conversation\n"
                "- Structure and maintain relevant information in the wiki\n"
                "- Use web_search and other tools when needed\n"
                "- Check existing wiki content for duplicates (kb_search, kb_list)\n"
                "- Mark clear deliverables for background jobs (job_role)\n\n"
                "## Working style\n\n"
                "- Wiki first, then external sources\n"
                "- Factual and aligned with project context\n"
                "- Make sources and assumptions transparent\n"
                "- Concise but with enough context for later use\n\n"
                "## Wiki structure\n\n"
                "Store results in the right folders: wiki/akteure/ (companies/people), "
                "wiki/recherche/ (sources), wiki/wissen/ (knowledge), wiki/ergebnisse/ "
                "(analyses and deliverables). On ingest follow the wiki-ingest skill.\n"
            )

        caps = out.get("suggested_capabilities") or []
        self.suggested_capabilities = [
            c for c in caps if isinstance(c, str) and c in SHARED_CAPS
        ]
        if not self.suggested_capabilities:
            self.suggested_capabilities = list(available_shared_capability_names())[:5]

        sks = out.get("suggested_skills") or []
        self.suggested_skills = []
        for s in sks[:6]:
            if isinstance(s, dict):
                self.suggested_skills.append(
                    SkillDraft(
                        title=str(s.get("title") or "Skill"),
                        description=str(s.get("description") or ""),
                        content=str(s.get("content") or ""),
                    )
                )
        if not self.suggested_skills:
            lbl = self.label
            self.suggested_skills = [
                SkillDraft(
                    title=f"{lbl} – Getting started",
                    description="Default workflow for the first task in this department",
                    content=(
                        "## When to use\n\n"
                        "- When a new task starts in this area\n"
                        "- When no suitable playbook exists in the wiki yet\n\n"
                        "## Steps\n\n"
                        "1. Clarify context and goal with the user or task description\n"
                        "2. Check the wiki for existing information (kb_search, kb_list)\n"
                        "3. Run research or analysis with the right tools\n"
                        "4. Structure results and cite sources\n"
                        "5. Save in the right wiki folder and add cross-links\n"
                    ),
                ),
                SkillDraft(
                    title=f"{lbl} – Wiki documentation",
                    description="Short checklist for clean wiki entries",
                    content=(
                        "## When to use\n\n"
                        "- Before saving a new or revised wiki page\n"
                        "- When multiple sources on one topic come together\n\n"
                        "## Steps\n\n"
                        "1. Pick a clear page title and one main focus\n"
                        "2. Choose folder (akteure, recherche, wissen, ergebnisse — see persona)\n"
                        "3. Set metadata and tags; avoid duplicates\n"
                        "4. Short summary at top, details and sources below\n"
                    ),
                ),
            ]

        self.phase = "confirm"
        cap_line = ", ".join(self.suggested_capabilities)
        preview = (
            f"{reply}\n\n"
            f"**Technical name:** `{self.dept_name}`  \n"
            f"**Label:** {self.label}  \n"
            f"**Capabilities:** {cap_line}  \n"
            f"**Skills:** {len(self.suggested_skills)} file(s)\n\n"
            "---\n\n"
            f"**Persona (excerpt):**\n{self.persona_draft[:1200]}"
        )
        if len(self.persona_draft) > 1200:
            preview += "\n\n[… persona truncated …]"

        preview += (
            "\n\n**Create department now?** Reply **yes** or **no** "
            "(or `/cancel`)."
        )
        return BuilderResponse(text=preview, phase="confirm")

    def _handle_confirm(self, raw: str) -> BuilderResponse:
        low = raw.lower().strip()
        if low in ("nein", "n", "no"):
            self.phase = "done"
            return BuilderResponse(
                text="Creation cancelled — no department created.",
                phase="done",
                done=True,
            )
        if low not in ("ja", "j", "yes", "y", "ok", "okay", "bestätigen", "bestaetigen"):
            return BuilderResponse(
                text="Please **yes** to create or **no** to cancel.",
                phase="confirm",
            )

        try:
            create_department_from_builder(
                root=self.root,
                registry=self.registry,
                engine=self.engine,
                cfg=self.cfg,
                name=self.dept_name,
                label=self.label,
                persona_content=self.persona_draft,
                capabilities=self.suggested_capabilities,
                skills=self.suggested_skills,
            )
        except ValueError as exc:
            self.phase = "done"
            return BuilderResponse(
                text=f"Error: {exc}",
                phase="done",
                done=True,
            )

        self.phase = "done"
        return BuilderResponse(
            text=(
                f"**Department `{self.dept_name}`** was created "
                f"(*{self.label}*). You can use it via `delegate` now."
            ),
            phase="done",
            done=True,
            created_department=self.dept_name,
        )
