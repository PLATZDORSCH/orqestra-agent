---
title: "Market Competitor Analysis"
description: "Full strategic competitor analysis — positioning, strengths/weaknesses, offering, pricing, team, and market share."
tags: [strategy, competitive-intelligence, analysis, market]
version: 1
created: "2026-04-08"
---

# Market Competitor Analysis

Comprehensive business-level competitor analysis — not SEO, but strategy: who are they, what do they offer, where are they strong, and where can you beat them.

## When to use

- User asks to analyze a competitor as a **business** (not just their website)
- User says "competitor analysis", "compare us to X", "competitive landscape", "what are their strengths?"
- Before entering a new market, launching a product, or repositioning
- For pitch decks, investor materials, or strategic planning

For **SEO-specific** competitor comparisons, use the `seo-competitor-analysis` skill instead.

## Steps

1. **Clarify scope**: Which competitor(s)? What industry/market? What decision does this analysis feed into (pricing, positioning, market entry)?

2. **Gather intelligence** (combine sources):
   - `kb_search` — check if the wiki already has a player profile or prior analysis
   - `fetch_url` — scrape the competitor's website: homepage, about, pricing, product pages, careers, press/news
   - `web_search` — recent press, funding rounds, partnerships, reviews, job postings

3. **Build the competitor profile** for each competitor:

   **Company overview**:
   - Name, founding year, HQ location, number of employees (estimate if needed)
   - Funding / ownership (bootstrapped, VC-backed, PE, public?)
   - Mission / positioning statement (from their website)
   - Key leadership (founders, CEO)

   **Product / service offering**:
   - Core products and services — what do they sell?
   - Target customer segments
   - Key differentiators they claim
   - Technology stack or delivery model (if relevant)

   **Pricing**:
   - Published pricing tiers or models (freemium, subscription, per-seat, project-based)
   - If no public pricing: estimate from job posts, case studies, or industry norms

   **Go-to-market**:
   - Sales model (self-serve, inside sales, field sales, channel/partner)
   - Marketing channels (content, paid, events, referrals)
   - Partnerships and integrations

   **Strengths**:
   - What are they genuinely good at?
   - Awards, certifications, notable clients
   - Market share or growth indicators

   **Weaknesses**:
   - Known pain points (from reviews, forums, job ads indicating gaps)
   - Missing features or segments not served
   - Organizational risks (high turnover, small team, tech debt signals)

4. **Comparative matrix**: Use `run_script` or a Markdown table to compare **our** offering vs. each competitor across dimensions that matter for the user's decision.

5. **Positioning map**: Use `generate_chart` (scatter or bar) to visualize where competitors sit on the two axes that matter most (e.g. price vs. breadth, specialization vs. scale).

6. **SWOT per competitor** (optional, if user wants depth):
   - Strengths / Weaknesses (internal to competitor)
   - Opportunities / Threats (external — for **us** relative to them)

7. **Strategic recommendations**: Based on the analysis:
   - Where are **gaps** we can exploit?
   - Where should we **avoid** direct competition?
   - Which competitor moves should we **monitor**?

8. **Save to wiki**:
   - Player profiles: `wiki/players/competitor-name.md` (one per competitor)
   - Synthesis: `wiki/synthesis/competitor-analysis-YYYY-MM-DD.md`
   - Follow CRITICAL RULES (index, overview, log, cross-references)

## Output format

```markdown
# Competitor Analysis: [Market / Context]
Date: [YYYY-MM-DD]

## Executive Summary
[2-3 sentences: key finding and recommended action]

## Competitors Analyzed

### [Competitor A]
| Dimension | Details |
|---|---|
| Founded | YYYY |
| HQ | City, Country |
| Employees | ~N |
| Funding | Bootstrapped / Series X / Public |
| Core offering | ... |
| Target segment | ... |
| Pricing model | ... |
| Key differentiator | ... |
| Strengths | ... |
| Weaknesses | ... |

### [Competitor B]
...

## Comparative Matrix
| Dimension | Us | Competitor A | Competitor B |
|---|---|---|---|
| Price range | €X–Y | €X–Y | €X–Y |
| Target segment | SMB | Enterprise | Mid-market |
| Core tech | ... | ... | ... |
| Geographic focus | DACH | Global | DACH |
| Differentiator | ... | ... | ... |

## Positioning Map
[Chart: e.g. price (y) vs. specialization (x)]

## Strategic Implications
### Opportunities (for us)
1. ...

### Threats (watch closely)
1. ...

### Recommendations
1. [Actionable next step]
2. ...
```

## Pitfalls

- Don't just list facts — interpret them for strategic relevance
- Distinguish between what competitors **claim** (marketing) and what they **deliver** (reviews, case studies)
- Missing public pricing ≠ no pricing strategy; often signals enterprise / high-touch sales
- Job postings reveal investment areas (e.g. hiring 10 ML engineers = AI push coming)
- Competitive analysis expires fast — note the date and plan for quarterly updates
- Avoid confirmation bias — report genuine competitor strengths honestly
