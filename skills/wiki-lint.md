---
title: "Wiki Lint"
description: "Run a health check on the wiki."
tags: [wiki, knowledge, maintenance]
version: 1
created: "2026-04-08"
---

# Wiki Lint

Run a health check on the wiki to find issues and improve quality.

## When to use

- User requests a lint, health check, or quality audit
- Periodically (e.g. weekly)
- After a large ingest series

## Steps

1. **Read all wiki pages** — Start with `wiki/index.md`, then read all referenced pages.

2. **Run checks:**

   **Contradictions** — Claims that contradict each other across pages. Check especially numbers, dates, and assessments.

   **Stale content** — Pages whose `updated` date is far in the past or whose claims may be outdated by newer sources. Set `status: stale` in frontmatter.

   **Orphan pages** — Pages that no other page links to. Every page SHOULD have at least 2 incoming links.

   **Missing "Related Pages"** — Pages that lack a "Related Pages" section or have fewer than 2 links there.

   **Missing bidirectionality** — Page A links to B, but B does not link back to A.

   **Missing pages** — Concepts, companies, or trends mentioned on multiple pages but without their own page.

   **Missing cross-references** — Pages that are thematically related but don't link to each other.

   **Data gaps** — Important topics based on only one or zero sources.

   **Index consistency** — Pages that exist but aren't in the index, or index entries pointing to non-existent pages.

   **Overview currency** — Is `wiki/overview.md` up to date? Does it reflect all processed sources?

3. **Create report** — Present results to the user, grouped by category.

4. **Write log entry** — Append to `wiki/log.md`:
   ```
   ## [YYYY-MM-DD] lint | Health check
   - Checked: X pages
   - Contradictions: X found
   - Orphan pages: X
   - Missing links: X
   - Missing pages: X
   - Overview current: yes/no
   - Recommendations: ...
   ```

5. **Suggest fixes** — Give the user concrete suggestions:
   - Which cross-references and back-references are missing
   - Which "Related Pages" sections need to be added
   - Which new pages should be created
   - Which sources should be found to fill gaps
   - Whether the overview needs updating

## Pitfalls

- No changes without user approval — only report and suggest
- For contradictions: present both positions, don't unilaterally pick one
- Log entry must NEVER be forgotten

## Verification

Before reporting completion:

1. All wiki pages and all subdirectories were checked
2. Report was presented to the user
3. `wiki/log.md` has a lint entry
4. Only then report completion.
