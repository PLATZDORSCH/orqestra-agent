---
title: "Financial Forecast"
description: "Build a revenue and cost forecast for 12-36 months."
tags: [finance, forecast, revenue, planning]
version: 1
created: "2026-04-08"
---

# Financial Forecast

Build a revenue and cost projection model for a business or product line.

## When to use

- User needs revenue projections for a pitch deck or business plan
- User wants to model growth scenarios (conservative, base, optimistic)
- User says "forecast", "revenue model", "financial plan", "P&L projection"

## Prerequisites

- Business model type (subscription, transactional, marketplace, etc.)
- Current metrics if available (MRR, customers, ARPU, churn)
- Or: assumptions about target market, pricing, and growth

## Steps

1. **Clarify the model**: What revenue model? What time horizon (12/24/36 months)? Which scenarios?

2. **Gather inputs from wiki**: Use `kb_search` for existing market data, pricing info, competitor benchmarks.

3. **Define assumptions table**:
   | Assumption | Conservative | Base | Optimistic |
   |---|---|---|---|
   | Monthly customer growth | X% | Y% | Z% |
   | ARPU | €X | €Y | €Z |
   | Monthly churn | X% | Y% | Z% |
   | Gross margin | X% | Y% | Z% |

4. **Build the model**: Use `run_script` to calculate month-by-month:
   - Revenue = customers × ARPU
   - New customers = existing × growth rate
   - Churned customers = existing × churn rate
   - Net customers = previous + new - churned
   - Costs: COGS, S&M, R&D, G&A (percentage of revenue or fixed)
   - EBITDA = Revenue - Total costs

5. **Generate charts**: Use `generate_chart` to create:
   - Revenue by month (line chart, all three scenarios)
   - Revenue breakdown by segment if applicable (stacked bar)
   - Cost structure (pie or waterfall)
   - Path to profitability (waterfall)

6. **Sensitivity analysis**: What happens if churn doubles? If ARPU drops 20%? Model 2-3 stress scenarios.

7. **Save to wiki**: Store the forecast in `wiki/synthesis/` with `kb_write`:
   - Path: `wiki/synthesis/financial-forecast-YYYY.md`
   - Tags: forecast, finance, revenue
   - Include all assumptions and scenarios

## Output format

```markdown
# Financial Forecast: [Product/Business]

## Assumptions
[Table of key assumptions per scenario]

## Revenue Projection
[Month-by-month table or summary by quarter]

## Cost Structure
[Fixed costs, variable costs, headcount plan]

## Scenario Comparison
| Metric | Conservative | Base | Optimistic |
|---|---|---|---|
| Year 1 Revenue | | | |
| Year 1 EBITDA | | | |
| Break-even month | | | |

## Key Risks
- ...

## Charts
[References to generated chart files]
```

## Pitfalls

- Always state assumptions explicitly — a forecast is only as good as its inputs
- Don't model more than 36 months — accuracy drops rapidly beyond that
- Include churn for subscription businesses — many forget it and overproject
- Use monthly granularity for year 1, quarterly for years 2-3
- Currency and year must be stated clearly
