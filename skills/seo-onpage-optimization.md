---
title: "SEO On-Page Optimization"
description: "Optimize a specific page for target keywords with actionable recommendations."
tags: [tech, seo, optimization, onpage]
version: 1
created: "2026-04-08"
---

# SEO On-Page Optimization

Analyze a specific page and provide concrete optimization recommendations.

## When to use

- User has a page that should rank better for a keyword
- User says "optimize this page", "why doesn't this page rank?", "on-page SEO"
- After keyword research, to optimize existing pages for target keywords

## Steps

1. **Get inputs**: Target URL and target keyword(s). If no keyword given, infer from page content and title.

2. **Analyze the live page**: Use **`analyze_page_seo`** for title, meta, headings, canonical, JSON-LD. Use **`fetch_url`** for a long **body text** extract for keyword checks (it also renders with Chromium by default).

3. **Analyze current state**:

   **Title tag**:
   - Current title and length
   - Does it contain the target keyword?
   - Is it compelling (would you click it in search results)?
   - Suggested optimized title

   **Meta description**:
   - Current description and length
   - Contains keyword + value proposition + CTA?
   - Suggested optimized description

   **URL structure**:
   - Is it clean and readable?
   - Contains keyword?
   - Too long or too deep?

   **H1**:
   - Present and unique?
   - Contains keyword?
   - Compelling to the reader?

   **Content analysis**:
   - Total word count
   - Keyword density (target: 1-2%, avoid stuffing)
   - Keyword in first 100 words?
   - Keyword in at least one H2?
   - Semantic variations and related terms used?
   - Content depth vs. top-ranking competitors

   **Internal links**:
   - How many internal links on the page?
   - Do anchor texts include relevant keywords?
   - Links to and from related pages?

   **External links**:
   - Any outbound links to authoritative sources?

4. **Competitor comparison**: Use `web_search` for the target keyword, fetch top 3 results:
   - How long is their content?
   - What subtopics do they cover that this page doesn't?
   - What's their heading structure?

5. **Generate recommendations**: Prioritized action list.

6. **Save**: `content/drafts/seo-optimization-YYYY-MM-DD-page.md`

## Output format

```markdown
# On-Page SEO: [URL]
Target keyword: [keyword]
Date: [YYYY-MM-DD]

## Current State
| Element | Current | Status | Recommendation |
|---|---|---|---|
| Title | "..." (XX chars) | ⚠️ | "..." (XX chars) |
| Meta description | "..." (XX chars) | ❌ | "..." (XX chars) |
| H1 | "..." | ✅ | — |
| URL | /path/ | ✅ | — |
| Word count | XXX | ⚠️ | Target: XXX+ |
| Keyword density | X.X% | ✅/⚠️ | Target: 1-2% |
| Internal links | X | ❌ | Add X links |

## Content Gap (vs. top 3 competitors)
| Subtopic | Us | #1 Result | #2 Result | #3 Result |
|---|---|---|---|---|
| [topic] | ❌ Missing | ✅ 200 words | ✅ 150 words | ❌ |

## Action Plan (by priority)

### Quick wins (< 30 min)
1. Update title to: "..."
2. Write meta description: "..."
3. Add keyword to first paragraph

### Content improvements (1-2 hours)
4. Add section on [missing subtopic]
5. Expand [thin section] from X to Y words
6. Add X internal links to [related pages]

### Advanced (ongoing)
7. Build internal links from [high-authority pages]
8. Add structured data markup for [type]
```

## Pitfalls

- Don't over-optimize — keyword stuffing hurts more than it helps
- Title should be written for humans first, search engines second
- Adding content isn't always the answer — sometimes restructuring is better
- Check that the page actually matches the search intent for the target keyword
- One page = one primary keyword cluster, not multiple unrelated keywords
