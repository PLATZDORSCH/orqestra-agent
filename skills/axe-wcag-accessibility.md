---
title: "Axe WCAG 2.2 Accessibility Audit"
description: "Run an automated accessibility test with axe-core scoped to WCAG 2.2 Level AA."
tags: [tech, accessibility, wcag, axe, a11y]
version: 1
created: "2026-04-08"
---

# Axe WCAG 2.2 Accessibility Audit

Use **Deque axe-core** in the browser to find WCAG issues on a page. The agent calls the tool **`axe_wcag_scan`**, which loads the official **axe-core** npm bundle and runs `axe.run()` with tags: `wcag2a`, `wcag2aa`, `wcag21aa`, `wcag22aa` (WCAG 2.2 Level AA scope in axe).

## When to use

- User asks for accessibility, a11y, WCAG, BITV/EN 301 549 alignment, or “barrier-free” checks
- Before launch or redesign of marketing pages, apps, or components
- After UI changes that might affect focus, labels, contrast, or semantics

## Steps

1. **Clarify scope**: Single URL vs. a small set of templates (home, main funnel, form, blog article). Automated scans are **page-level** — test representative URLs.

2. **Run the scan**: Call **`axe_wcag_scan`** with each URL. Ensure Playwright + Chromium are installed (`[browser]` extra). The tool needs **network access** once per run to load the pinned **axe-core** script from jsDelivr (same library as `npm install axe-core`).

3. **Interpret results**:
   - **`violations`**: Definite failures — prioritize by `impact` (critical → serious → moderate → minor)
   - **`incomplete`**: Needs manual review (e.g. contrast when background image unknown)
   - Use `helpUrl` links to Deque’s rule documentation

4. **Do not claim full WCAG compliance** from automation alone — axe covers many but not all success criteria; manual testing (keyboard, screen reader, zoom) is still required for audits.

5. **Document**: Save findings to `wiki/synthesis/` or `content/drafts/` with URL, date, violation summary, and remediation priorities.

## Output format (report)

```markdown
# Accessibility scan (axe-core / WCAG 2.2 AA tags)
- URL: …
- Date: …
- Tool: axe-core [version from result]

## Summary
- Violations: X
- Incomplete (manual review): X
- Passes (informational): X

## Critical / Serious
| Rule ID | Impact | Issue | Sample selectors |
|---|---|---|---|
| … | … | … | … |

## Moderate / Minor
…

## Incomplete (follow-up)
…

## Recommendations
1. …
```

## Pitfalls

- **SPAs**: Use default `networkidle` so the DOM is stable before axe runs
- **Auth / paywalls**: axe only sees what the browser session sees — logged-in pages may need credentials outside this tool
- **iframes**: axe analyzes the main frame; nested iframes may need separate URLs or extended setup (not in v1)
- **CDN**: If the axe script cannot load (offline air-gap), the tool errors — use an environment with outbound HTTPS or vendor axe locally in a future iteration
- **Legal**: Automated results support remediation planning; they are not a certificate of conformity
