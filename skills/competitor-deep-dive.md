---
title: "Competitor Deep Dive"
description: "Build a comprehensive competitor profile from public sources."
tags: [competitive-intelligence, research, analysis]
version: 1
created: "2025-01-01"
---

# Competitor Deep Dive

## When to use

When the user wants a detailed analysis of a specific competitor, or when building the knowledge base with competitor profiles.

## Prerequisites

- Competitor name (and optionally their website URL)
- Understanding of which industry/market to contextualize them in

## Steps

1. **Check existing knowledge**: Search the knowledge base with `kb_search` for any prior entries on this competitor.

2. **Company basics** — Fetch and extract from their website:
   - Headquarters, founding year, employee count
   - Funding history (check Crunchbase, PitchBook)
   - Key leadership team
   - Mission statement / positioning

3. **Product analysis** — Map their offering:
   - Core features and product lines
   - Pricing model and tiers (fetch their pricing page)
   - Target audience and ideal customer profile
   - Technology stack (check job postings on their careers page, BuiltWith, StackShare)

4. **Market position**:
   - Market share estimates (analyst reports, press releases)
   - Key partnerships and integrations
   - Geographic presence
   - Notable customers (case studies, logos on their site)

5. **Strengths and weaknesses**:
   - Read customer reviews on G2, Capterra, Trustpilot
   - Check social media sentiment
   - Look for recurring complaints or praise patterns

6. **Recent developments**:
   - Search for recent news, product launches, funding rounds
   - Check their blog for strategic announcements

7. **Synthesize**: Write a structured profile following the output format below.

8. **Persist to knowledge base**: Save with `kb_write`:
   - Path: `competitors/<slug>.md`
   - Include all metadata fields: title, category, industry, region, revenue_range, founded, tags
   - Add references to related market entries and other competitor profiles

## Output format

```markdown
# [Company Name]

## Profile
- **Headquarters**: ...
- **Founded**: ...
- **Employees**: ...
- **Funding**: ...
- **Customers**: ...

## Product
[Description, key features, pricing]

## Strengths
- ...

## Weaknesses
- ...

## Recent developments
- ...

## Sources
- [Source 1](url)
- [Source 2](url)
```

## Tips

- Pricing pages change frequently — always note the date you checked
- Job postings reveal strategic direction (e.g. hiring ML engineers = AI push)
- Don't rely on a single review source; cross-reference G2 and Capterra
- If data is scarce, note it explicitly rather than speculating
