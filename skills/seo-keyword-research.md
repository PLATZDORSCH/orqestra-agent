---
title: "SEO Keyword Research"
description: "Research and prioritize keywords for an SEO or content strategy."
tags: [tech, seo, keywords, content, research]
version: 1
created: "2026-04-08"
---

# SEO Keyword Research

Build a prioritized keyword list for content planning and on-page optimization.

## When to use

- User wants to find the right keywords to target
- User says "keyword research", "what keywords should we target?", "SEO keywords"
- Starting a new content strategy or entering a new market

## Steps

1. **Define seed topics**: Start with 3-5 core topics related to the business. Use `kb_search` for existing market and product knowledge.

2. **Expand with search**: For each seed topic, use `web_search` to find:
   - Related long-tail keywords
   - "People also ask" type questions
   - Autocomplete suggestions (search for partial queries)
   - Related searches at the bottom of results

3. **Categorize by search intent**:
   | Intent | Signal words | Example | Content type |
   |---|---|---|---|
   | Informational | what, how, why, guide | "what is CRM" | Blog, guide |
   | Commercial | best, vs, comparison, review | "best CRM for SMB" | Comparison page |
   | Transactional | buy, pricing, demo, trial | "CRM pricing" | Landing page |
   | Navigational | [brand name], login | "Salesforce login" | Skip (branded) |

4. **Assess competition**: For each keyword, search and analyze:
   - Who ranks on page 1?
   - Are they big brands or smaller sites?
   - Content quality and depth of top results
   - Can we realistically compete?

5. **Estimate difficulty** (without paid tools):
   - Easy: Page 1 has forums, thin content, old articles
   - Medium: Page 1 has decent content but no dominant brands
   - Hard: Page 1 is all big brands, in-depth guides, high authority

6. **Prioritize**: Use `run_script` to create a scoring matrix:
   ```
   Priority = Relevance × (1 / Difficulty) × Business value
   ```
   - Relevance: How closely does this match our offering? (1-3)
   - Difficulty: How hard to rank? (1=easy, 3=hard)
   - Business value: Does traffic convert? (1-3)

7. **Group into clusters**: Keywords with similar intent should target the same page. One page per cluster, not one page per keyword.

8. **Generate chart**: Use `generate_chart` to visualize keyword priority (scatter plot: difficulty vs. business value).

9. **Save**: `wiki/synthesis/keyword-research-YYYY-MM-DD.md`

## Output format

```markdown
# Keyword Research: [Business/Product]
Date: [YYYY-MM-DD]

## Seed Topics
1. [Topic] — [Why relevant]
2. ...

## Keyword List

### High Priority (Easy + High Value)
| Keyword | Intent | Difficulty | Value | Target page |
|---|---|---|---|---|
| ... | Commercial | Easy | High | /comparison |

### Medium Priority
| Keyword | Intent | Difficulty | Value | Target page |
|---|---|---|---|---|

### Long-term (Hard but valuable)
| Keyword | Intent | Difficulty | Value | Target page |
|---|---|---|---|---|

## Keyword Clusters
### Cluster: [Topic]
- Primary: [main keyword]
- Secondary: [related keyword 1], [related keyword 2]
- Questions: [question keyword]
- Target page: [URL or page to create]

## Content Gaps
[Keywords where we have no content at all]

## Quick Wins
[Easy keywords we can target with small content updates]

## Recommendations
1. [First keyword cluster to target and why]
2. ...
```

## Pitfalls

- Don't chase high-volume keywords without considering difficulty
- Long-tail keywords (4+ words) often convert better than head terms
- One page should target a cluster of related keywords, not just one keyword
- Search intent mismatch kills rankings — don't put a sales page on an informational query
- Revisit every 3-6 months — search behavior changes
