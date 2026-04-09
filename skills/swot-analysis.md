---
title: "SWOT Analysis"
description: "Conduct a structured SWOT analysis for a company, product, or market position."
tags: [analysis, strategy, frameworks]
version: 1
created: "2025-01-01"
---

# SWOT Analysis

## When to use

When the user asks for a strengths/weaknesses assessment, competitive positioning review, or strategic evaluation of a company or product.

## Prerequisites

- Company or product name to analyze
- Ideally: existing knowledge base entries about the subject and its competitors

## Steps

1. **Gather context**: Use `kb_search` to check for existing entries about the company and its market. Use `kb_related` to find connected documents.

2. **Research gaps**: If knowledge is incomplete, use `web_search` and `fetch_url` to gather:
   - Company website (about page, product page, pricing)
   - Recent news and press releases
   - Customer reviews (G2, Capterra, Trustpilot)
   - Competitor comparison pages

3. **Build the SWOT matrix**:
   - **Strengths** (internal, positive): What does the company do well? Unique resources, capabilities, market position?
   - **Weaknesses** (internal, negative): Where does it fall short? Resource gaps, operational issues?
   - **Opportunities** (external, positive): Market trends, unserved segments, regulatory changes that could help?
   - **Threats** (external, negative): Competitive pressure, market shifts, technology disruption?

4. **Add specificity**: Each point should include concrete evidence — data points, quotes, or source references. Avoid vague statements like "strong brand" without supporting detail.

5. **Derive implications**: After the matrix, write a "So what?" section with 2–3 strategic implications or recommended actions.

6. **Persist results**: Save the analysis to the knowledge base with `kb_write`:
   - Path: `companies/<slug>.md` or `competitors/<slug>.md`
   - Category: `companies` or `competitors`
   - Tags: include `swot` plus relevant industry/region tags
   - References: link to related market and competitor entries

## Output format

```markdown
## SWOT Analysis: [Company Name]

### Strengths
- Point 1 (source)
- Point 2 (source)

### Weaknesses
- Point 1 (source)
- Point 2 (source)

### Opportunities
- Point 1 (source)
- Point 2 (source)

### Threats
- Point 1 (source)
- Point 2 (source)

### Strategic implications
1. ...
2. ...
3. ...
```

## Common pitfalls

- Listing too many vague points — better to have 3 well-evidenced items per quadrant than 10 generic ones
- Confusing internal factors (S/W) with external factors (O/T)
- Forgetting to cite sources — every claim should be traceable
- Not connecting the SWOT to actionable recommendations
