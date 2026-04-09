---
title: "Market Sizing (TAM/SAM/SOM)"
description: "Estimate total addressable market, serviceable market, and obtainable market for a product or segment."
tags: [market-analysis, sizing, strategy, frameworks]
version: 1
created: "2025-01-01"
---

# Market Sizing (TAM / SAM / SOM)

## When to use

When the user needs market size estimates for business planning, investor decks, or go-to-market strategy.

## Prerequisites

- Clear definition of the product or service
- Target geography and customer segment

## Steps

1. **Define the market clearly**: What product category? Which customer segment? Which geography? Ambiguity here ruins the entire estimate.

2. **Choose approach** — use both if possible:
   - **Top-down**: Start from industry reports (Statista, Gartner, IDC, Forrester) and narrow down by segment/geography
   - **Bottom-up**: Count potential customers × average revenue per customer

3. **TAM (Total Addressable Market)**:
   - The entire global revenue opportunity if you had 100% market share
   - Use `web_search` to find industry reports and analyst estimates
   - Fetch and extract key data points with `fetch_url`

4. **SAM (Serviceable Addressable Market)**:
   - The portion of TAM you can actually reach with your product, pricing, and distribution
   - Filter by: geography, customer segment, price point compatibility, language, regulatory access

5. **SOM (Serviceable Obtainable Market)**:
   - Realistic short-term capture (1–3 years) given competition and go-to-market constraints
   - Typically 1–5% of SAM for new entrants, 10–20% for established players in growing markets

6. **Validate with bottom-up cross-check**:
   - Use `run_script` to calculate:
     ```python
     potential_customers = segment_size * fit_percentage
     som = potential_customers * avg_deal_size * expected_win_rate
     ```

7. **Document assumptions**: Every number must have a source or a clearly stated assumption. Create a table of assumptions.

8. **Persist**: Save to knowledge base with `kb_write`:
   - Path: `markets/<slug>.md`
   - Tags: include `tam`, `sam`, `som`, industry, region

## Output format

```markdown
## Market Sizing: [Product/Segment]

### Definitions
- Product: ...
- Geography: ...
- Customer segment: ...

### TAM: $X billion
[Methodology and sources]

### SAM: $X billion
[Filters applied and reasoning]

### SOM: $X million (Year 1–3)
[Assumptions: win rate, sales capacity, competitive landscape]

### Key assumptions
| Assumption | Value | Source |
|------------|-------|--------|
| ... | ... | ... |

### Bottom-up validation
[Calculation details]
```

## Common pitfalls

- Citing a TAM number without specifying geography or timeframe
- Confusing TAM with SAM (very common in pitch decks)
- Using a single source — cross-reference at least two independent estimates
- Forgetting currency and year (EUR 2024 vs USD 2025 makes a big difference)
- SOM that's unrealistically high (>10% of SAM for a startup)
