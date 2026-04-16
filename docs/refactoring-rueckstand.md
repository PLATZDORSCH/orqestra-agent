# Refactoring — offene Punkte (Nacharbeit)

Dieses Dokument fasst zusammen, was nach der Aufteilung der Monolithen (`core/departments`, `capabilities/knowledge`, `gateway_api` → `api/`) **noch nicht** oder nur teilweise angepasst ist — sowie was inzwischen erledigt wurde.

## Bereits erledigt (Kontext)

- `core/departments.py` → Fassade; Logik in `deep_work.py`, `proactive.py`, `jobs.py`, `department.py`, `registry.py`
- `capabilities/knowledge.py` → Fassade; `kb_core.py`, `kb_capabilities.py`
- `gateway_api.py` → dünner Wrapper; `api/` enthält `app.py`, `state.py`, `run_api`, `models`, `constants`, `language_utils` und Router: `sessions`, `chat`, `wiki`, `departments`, `jobs`, **`pipelines`**, **`project`**, **`settings`**
- Unit-Tests unter `tests/` (pytest)
- **Packaging**: Paket `orqestra` unter `src/orqestra/` (siehe `pyproject.toml`); **keine** `sys.path`-Hacks mehr für den normalen Install
- **Docker**: `Dockerfile` kopiert `src/` inkl. `api/`, `core/`, `capabilities/` sowie **`templates/`** (für Template-Installer im Container)
- **CI**: GitHub Actions führt `pytest` aus (siehe `.github/workflows/test.yml`)
- **`requirements.txt`**: nur noch `-e .[…]` + Test-Extra; **Source of truth** für Runtime-Deps ist **`pyproject.toml`**
- **`core/registry.py`**: Fassade; Implementierung aufgeteilt in `registry_core.py`, `registry_yaml.py`, `registry_persona.py`, `registry_jobs.py`, `registry_delegate.py`
- **`capabilities/kb_core.py`**: Fassade; Implementierung aufgeteilt in `kb_fts.py`, `kb_base.py`, `kb_navigation.py`

---

## 1. Dokumentation (README & Projektstruktur)

- [x] Im **README** den Abschnitt **Project structure** aktualisiert: `api/`, `src/orqestra/`, Router-Module, Fassaden.
- [x] **HTTP-Einstieg**: empfohlen `uvicorn orqestra.api.app:app`; alternativ `uvicorn orqestra.gateway_api:app` (re-exportiert `app`).
- [x] Kurzbeschreibung: `api/app.py` registriert Router aus `api/*.py`.

---

## 2. Packaging & Entwickler-Setup

- [x] Nach `git clone` und `pip install -e ".[test]"`: `python -c "from orqestra.api import app"` funktioniert.
- [x] **`requirements.txt`** vs. **`pyproject.toml`**: dokumentiert — `pyproject.toml` ist Source of truth; `requirements.txt` delegiert per `-e .`.

---

## 3. CI / Qualitätssicherung

- [x] **pytest** in CI (GitHub Actions).
- [ ] Optional: `ruff` / `mypy` nur für `src/orqestra/api/` und `capabilities/` schrittweise aktivieren.

---

## 4. Code — optionale Verbesserungen (kein Muss)

- [x] **`api/state.py`**: `mount_web_ui()` aus `run_api()` und Lifespan — `_web_ui_mounted` verhindert Doppel-Mount; **`state.init()`** ist idempotent (`_ready`); Lifespan ruft `load_config()` auf, `run_api(cfg)` übergibt explizite Config — siehe Kommentare in `api/app.py` / `api/state.py`.
- [x] **`sys.path` / ein Ort für Pfad-Setup**: durch **`src`-Layout** und installierbares Paket `orqestra` erledigt (kein `sys.path.insert` in Entrypoints).
- [ ] **Tests erweitern**: Integrationstest mit `TestClient` für 1–2 Routen (`/api/departments`, `/api/wiki/tree`), falls Regressionen in der Router-Verkabelung vermieden werden sollen (braucht initialisiertes `state` / Config-Mocks).

---

## 5. Docker & Deployment

- [x] **`Dockerfile`** kopiert `src/` und **`templates/`**; nach Refactorings Build-Cache invalidieren, falls Layer alt sind.

---

## 6. Bekannte Laufzeit-Hinweise

- **FastAPI** `Form`/`Upload` benötigt **`python-multipart`** — in `pyproject.toml`; ohne Paket schlagen Imports von Routen mit Upload/Form fehl. Bei Support-Fällen `pip install -e ".[browser]"` bzw. volle Extras prüfen.

---

## 7. Nächste Refactor-Kandidaten (Fassade + Submodule, optional)

Größe (Stand, grob): `core/registry.py` Fassade; Implementierung aufgeteilt — **nächste große Monolithen**:

| Modul | Zeilen (ca.) | Hinweis |
|-------|----------------|--------|
| `core/department_builder.py` | ~980 | Wizard + Installer |
| `core/pipelines.py` | ~762 | PipelineRunner |
| `gateway_telegram.py` | ~707 | Bot-Gateway |
| `core/engine.py` | ~657 | StrategyEngine |
| `api/wiki.py` | ~620 | Wiki-Router |
| `capabilities/skills.py` | ~572 | Skill-Verwaltung |

- `core/engine.py`, `core/bootstrap.py` — nur bei Bedarf ähnlich splitten.
- Frontend (`web/`) — API-Pfade unverändert (`/api/...`).

---

## 8. Roadmap — echter Knowledge Graph (aktuell nur Link-Graph)

Die Wiki-Graph-Ansicht (`/api/wiki/graph`) ist heute ein **Obsidian-artiger Link-Graph** über Markdown-Seiten (Nodes = Seiten, Edges = Markdown-Links + geteilte Tags + Job-Gruppen). Sie ist **kein semantischer Knowledge Graph**. Wenn der Anspruch gestellt wird, einen echten KG zu bauen, sind mindestens folgende Bausteine nötig:

- [ ] **Entity-/Relation-Extraction** aus Fließtext (LLM-gestützt beim Index-Lauf) — typisierte Entitäten (Person, Firma, Produkt, Markt …) und typisierte Relationen (`competes_with`, `acquired`, `located_in` …).
- [ ] **Separate Tabellen** `entities` und `relations` (SQLite genügt zum Start) — unabhängig von der bestehenden `links`-Tabelle.
- [ ] **Entity Resolution / Aliase** (z. B. „Stripe", „Stripe Inc.", „stripe.com" → eine Entität).
- [ ] **Graph-Queries** (Traversals, k-Hop, Pfade) — entweder via rekursive CTEs in SQLite oder ein dedizierter Store (Neo4j / DuckDB-PGQ / NetworkX im Memory).
- [ ] **Eigener API-Endpoint** (z. B. `/api/wiki/kgraph`) — der bestehende Link-Graph-Endpoint bleibt, damit die Visualisierung nicht bricht.
- [ ] **UI-Trennung**: Link-Graph vs. Knowledge Graph als zwei klar benannte Ansichten.

Bis dahin: Benennung überall bei „Link-Graph" / „Obsidian-style graph" belassen, nicht „Knowledge Graph".

---

## 9. Sonstiges (Security / Cleanup)

- [x] **CORS**: `allow_credentials=False` bei `allow_origins=["*"]` — Auth läuft über `Authorization: Bearer`, nicht über Cookies.
- [x] **egg-info-Altlast**: veraltetes `orch_agent.egg-info` entfernt; `*.egg-info/` in `.gitignore`.

---

*Stand: nach src-Layout, Registry-/KB-Split, CI, Docker-`templates/`-Fix. Bei größeren Änderungen an `src/orqestra/` dieses Dokument mit aktualisieren.*
