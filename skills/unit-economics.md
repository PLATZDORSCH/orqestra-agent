---
title: "Unit Economics (CAC / LTV)"
description: "Calculate customer acquisition cost, lifetime value, and payback period."
tags: [finance, unit-economics, cac, ltv, saas]
version: 1
created: "2026-04-08"
---

# Unit Economics (CAC / LTV)

Calculate the core unit economics that determine whether a business model is viable.

## When to use

- User wants to evaluate business model viability
- User asks about CAC, LTV, payback period, LTV/CAC ratio
- User is preparing for investor conversations or pricing decisions

## Steps

1. **Gather data**: Ask the user for (or research via `kb_search` / `web_search`):
   - **Sales & marketing spend** per month/quarter
   - **New customers acquired** in the same period
   - **Average revenue per user (ARPU)** per month
   - **Gross margin** percentage
   - **Monthly churn rate** (or average customer lifetime)

2. **Calculate CAC**:
   ```
   CAC = Total S&M spend / New customers acquired
   ```
   Break down by channel if data available (paid, organic, referral, outbound).

3. **Calculate LTV**:
   ```
   Average customer lifetime = 1 / monthly churn rate
   LTV = ARPU × Gross margin × Average lifetime (months)
   ```

4. **Calculate payback period**:
   ```
   Payback = CAC / (ARPU × Gross margin)  → in months
   ```

5. **Evaluate ratios**: Use `run_script` for calculations and `generate_chart` for visualization.
   - **LTV/CAC ratio**: >3x is healthy, <1x is burning cash
   - **Payback period**: <12 months for SaaS, <18 months acceptable
   - **CAC by channel**: Which channels are most efficient?

6. **Benchmark against industry**: Use `web_search` for SaaS/industry benchmarks. Typical SaaS:
   - LTV/CAC: 3-5x
   - Payback: 5-12 months
   - Gross margin: 70-85%

7. **Generate visualization**: Create a chart showing LTV vs CAC, payback timeline.

8. **Save to wiki**: `wiki/synthesis/unit-economics-[product].md`

## Output format

```markdown
# Unit Economics: [Business/Product]

## Key Metrics
| Metric | Value | Benchmark | Status |
|---|---|---|---|
| CAC | €X | €Y (industry) | ✅/⚠️/❌ |
| LTV | €X | €Y (industry) | ✅/⚠️/❌ |
| LTV/CAC | X.Xx | >3x | ✅/⚠️/❌ |
| Payback | X months | <12 months | ✅/⚠️/❌ |
| Monthly churn | X% | <3% | ✅/⚠️/❌ |
| Gross margin | X% | >70% | ✅/⚠️/❌ |

## CAC Breakdown by Channel
[Table or chart]

## Recommendations
1. ...
```

## Pitfalls

- Don't confuse blended CAC with paid CAC — organic customers dilute the number
- LTV calculation requires gross margin, not revenue — a common mistake
- For early-stage: use cohort-based churn, not simple average
- Always state the time period of the input data
