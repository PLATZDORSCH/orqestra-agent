---
title: "Wiki Query"
description: "Answer a question based on compiled wiki knowledge."
tags: [wiki, knowledge, query]
version: 1
created: "2026-04-08"
---

# Wiki Query

Answer a question based on compiled wiki knowledge.

## When to use

- User asks a factual question about the industry or domain
- User wants an assessment, analysis, or contextualization
- User says "what do we know about...", "how is... doing", etc.

## Steps

1. **Read the index** — Use `kb_read` on `wiki/index.md` to identify relevant pages.

2. **Read relevant pages** — Read all thematically matching wiki pages. When in doubt, read more rather than fewer.

3. **Synthesize an answer** — Formulate the answer with:
   - References to wiki pages as evidence
   - Clear labeling when something is based on few sources
   - Marking contradictions or uncertainties

4. **Check if worth saving** — If the answer is substantial (analysis, comparison, new insight): save as a new page in `wiki/synthesis/` using `kb_write`:
   - Path: `wiki/synthesis/analysis-topic.md`
   - Metadata: title, category=synthesis, tags, sources (list of referenced pages), created, updated, status=active
   - The page needs a "Related Pages" section with at least 2 bidirectional links

5. **Update index, overview, and log** — If a new page was created:
   - `wiki/index.md` → new entry under Synthesis
   - `wiki/overview.md` → if the analysis contains new insights
   - `wiki/log.md` → entry with `query | Question title`

## Pitfalls

- Always read the index first, never guess
- If the wiki doesn't have enough information: say so openly and name the knowledge gaps
- Trivial questions don't need to be saved as synthesis pages
- If saved: index, overview, and log updates must NEVER be forgotten

## Verification

Before reporting completion:

1. Answer is based on actual wiki pages, not general knowledge
2. If saved: new page has correct frontmatter AND "Related Pages" section
3. If saved: `wiki/index.md` contains the new page
4. If saved: `wiki/log.md` has an entry
5. Only then report completion.
