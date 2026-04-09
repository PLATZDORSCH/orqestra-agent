---
title: "SEO Site Audit"
description: "Run a comprehensive technical SEO audit on a website."
tags: [tech, seo, audit, performance]
version: 1
created: "2026-04-08"
---

# SEO Site Audit

Perform a full technical SEO health check on a website.

## When to use

- User wants a technical SEO audit of their site or a competitor's
- User says "check my SEO", "site audit", "technical SEO problems"
- Before a redesign or migration to document the baseline

## Steps

1. **Render the homepage in a real browser**: Use **`analyze_page_seo`** on the main URL for **SEO metadata** (`document_title`, `meta`, `link_rels`, `headings`, `json_ld`, `detected_issues`, etc.). Both `analyze_page_seo` and `fetch_url` use headless Chromium when Playwright is installed; use `analyze_page_seo` as the source of truth for meta/structured data, and `fetch_url` if you also need long extracted body text.

2. **Check critical pages**: Run **`analyze_page_seo`** on 5–10 key URLs (same list as below).

   - Homepage
   - Main service/product pages
   - Blog/content hub
   - Contact page
   - A deep-linked page (3+ clicks from home)

3. **For each page, check** (use fields from `analyze_page_seo`):

   **Title tag**:
   - Present? Unique across pages?
   - Length: 50-60 chars optimal
   - Contains primary keyword?
   - Brand at end (not beginning)?

   **Meta description**:
   - Present? Unique?
   - Length: 150-160 chars
   - Contains keyword + CTA?

   **Headings**:
   - Exactly one H1 per page?
   - H1 contains primary keyword?
   - Logical heading hierarchy (H1 → H2 → H3)?

   **Content**:
   - Word count (thin content < 300 words is a red flag)
   - Keyword presence in first 100 words?
   - Internal links present?
   - External authoritative links?

   **Images**:
   - Alt text present?
   - Descriptive filenames (not IMG_1234.jpg)?

   **Structured data**:
   - From `json_ld` and `structured_data_types`: Organization, WebSite, Product, Article, FAQPage, BreadcrumbList, etc.
   - Fix any `json_ld_parse_error` entries in `detected_issues`.

4. **Technical checks** (use `run_script` with httpx where needed):

   **Robots.txt**: Fetch `/robots.txt` — is the site blocking important paths?
   **Sitemap**: Fetch `/sitemap.xml` — exists? How many URLs? Any errors?
   **HTTPS**: All pages on HTTPS? No mixed content?
   **Canonical tags**: Confirm from `link_rels.canonical` vs `final_url` in `analyze_page_seo`.
   **Redirect chains**: Compare requested URL to `final_url` and `http_status`.

5. **Performance check**: Use `run_script` to measure:
   - Response time per page
   - Page size (HTML)
   - Number of redirects

6. **Compile findings**: Categorize issues by severity:
   - 🔴 Critical (blocks indexing, broken functionality)
   - 🟡 Warning (hurts rankings, bad UX)
   - 🟢 Opportunity (could improve performance)

7. **Save to wiki**: `wiki/synthesis/seo-audit-YYYY-MM-DD-domain.md`

## Output format

```markdown
# SEO Audit: [domain.com]
Date: [YYYY-MM-DD]

## Summary
- Pages checked: X
- Critical issues: X
- Warnings: X
- Opportunities: X

## Critical Issues 🔴
| Issue | Page | Details | Fix |
|---|---|---|---|
| Missing title | /about | No <title> tag | Add unique title |

## Warnings 🟡
| Issue | Page | Details | Fix |
|---|---|---|---|

## Opportunities 🟢
| Issue | Page | Details | Fix |
|---|---|---|---|

## Page-by-Page Analysis

### Homepage (/)
- Title: "..." (XX chars) ✅/❌
- Meta description: "..." (XX chars) ✅/❌
- H1: "..." ✅/❌
- Word count: XXX
- Internal links: X
- Load time: X.Xs

### [Page 2]
...

## Technical
- robots.txt: ✅/❌ [details]
- sitemap.xml: ✅/❌ [X URLs]
- HTTPS: ✅/❌
- Canonical tags: ✅/❌

## Priority Action Plan
1. [Critical fix 1]
2. [Critical fix 2]
3. [Warning fix 1]
```

## Pitfalls

- Don't just list problems — prioritize by impact and effort
- Check mobile viewport meta tag — Google uses mobile-first indexing
- Look for duplicate title/description across pages — very common issue
- robots.txt blocking CSS/JS breaks rendering in Google's eyes
- A sitemap with errors is worse than no sitemap
