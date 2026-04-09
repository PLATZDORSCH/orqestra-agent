---
title: "SEO Competitor Analysis"
description: "Analyze a competitor's SEO strategy — keywords, content, backlinks, and technical setup."
tags: [tech, seo, competitive-intelligence, analysis]
version: 1
created: "2026-04-08"
---

# SEO Competitor Analysis

Reverse-engineer a competitor's SEO strategy to find opportunities.

## When to use

- User wants to understand why a competitor ranks higher
- User says "SEO competitor analysis", "why do they rank?", "compare our SEO"
- Planning content strategy and need to understand the competitive landscape

## Steps

1. **Identify competitors**: If not given, use `web_search` for the user's main keywords and note the top 3-5 domains that consistently appear.

2. **Analyze each competitor's site** (use **`analyze_page_seo`** for title/meta/H1/JSON-LD; use `fetch_url` only if you need long body text for content comparison):

   **Homepage**:
   - Title tag strategy (brand positioning)
   - Meta description approach
   - H1 message
   - Content length and structure

   **Top-ranking pages**:
   - Search for key industry terms, fetch the competitor pages that rank
   - Analyze their content structure, length, and depth
   - Note internal linking patterns

3. **Keyword strategy analysis**:
   - Search for 10-20 industry keywords with `web_search`
   - Track which competitor appears for each
   - Build a keyword coverage matrix

   | Keyword | Us | Competitor A | Competitor B |
   |---|---|---|---|
   | "crm software" | #12 | #3 | #5 |
   | ... | | | |

4. **Content strategy analysis**:
   - Fetch competitor blog/content hub
   - Estimate publishing frequency
   - Identify content pillars/themes
   - Note content formats (guides, comparisons, tools, data studies)
   - Check content length patterns

5. **Technical comparison** (use `run_script`):
   - Response time comparison
   - HTTPS status
   - sitemap.xml size (proxy for indexed pages)
   - robots.txt differences

6. **Link profile estimation**:
   - Use `web_search` for `site:competitor.com` to estimate indexed pages
   - Use `web_search` for `"competitor.com" -site:competitor.com` to find who links to them
   - Note any guest posts, press coverage, partner pages

7. **Gap analysis**: Where do competitors have content that we don't?

8. **Save**: `wiki/synthesis/seo-competitor-analysis-YYYY-MM-DD.md`

## Output format

```markdown
# SEO Competitor Analysis
Date: [YYYY-MM-DD]

## Competitors Analyzed
| Domain | Estimated pages | Focus keywords | Strength |
|---|---|---|---|
| competitor-a.com | ~500 | CRM, sales | Content depth |
| competitor-b.com | ~200 | CRM, SMB | Technical SEO |

## Keyword Coverage Matrix
| Keyword | Search intent | Us | Comp A | Comp B |
|---|---|---|---|---|
| ... | Informational | — | #3 | #7 |

## Content Strategy Comparison
| Metric | Us | Comp A | Comp B |
|---|---|---|---|
| Blog post count | X | X | X |
| Publishing frequency | X/month | X/month | X/month |
| Avg. content length | X words | X words | X words |
| Content formats | ... | ... | ... |

## Content Gap Analysis
[Topics competitors cover that we don't]

## Technical Comparison
| Metric | Us | Comp A | Comp B |
|---|---|---|---|
| Response time | Xs | Xs | Xs |
| Indexed pages | ~X | ~X | ~X |
| HTTPS | ✅/❌ | ✅/❌ | ✅/❌ |

## Opportunities
1. [Keyword gap we can fill]
2. [Content format they use that works]
3. [Technical advantage we can gain]

## Threats
1. [Where competitors are pulling ahead]
```

## Pitfalls

- Don't just copy competitor strategy — understand the WHY behind it
- Indexed page count ≠ quality; a site with 100 great pages beats 1000 thin ones
- Search results are personalized — use incognito/neutral queries
- Competitors may rank for branded terms that aren't achievable for you
- Update this analysis quarterly — SEO landscapes shift fast
