---
title: "Break-Even Analysis"
description: "Calculate the break-even point for a product, project, or business."
tags: [finance, break-even, planning, investment]
version: 1
created: "2026-04-08"
---

# Break-Even Analysis

Determine when revenue covers all costs — the point of profitability.

## When to use

- User is evaluating a new product launch or investment
- User needs to justify a project or hiring decision
- User asks "when will this be profitable?", "how many units do we need to sell?"

## Steps

1. **Identify cost structure**:
   - **Fixed costs**: Rent, salaries, tools, subscriptions — costs that don't change with volume
   - **Variable costs per unit**: COGS, transaction fees, shipping, commissions
   - **One-time investments**: Development, setup, equipment

2. **Define revenue per unit**:
   - Price per unit / subscription / transaction
   - Consider discounts and average selling price vs. list price

3. **Calculate break-even point**: Use `run_script`:
   ```
   Contribution margin = Price per unit - Variable cost per unit
   Break-even units = Fixed costs / Contribution margin
   Break-even revenue = Break-even units × Price per unit
   ```

4. **Time-based break-even** (for recurring revenue):
   ```
   Monthly contribution = (New customers × ARPU × Gross margin) - Monthly fixed costs
   → Find the month where cumulative contribution > initial investment
   ```

5. **Visualize**: Use `generate_chart`:
   - Revenue vs. cost lines crossing (line chart)
   - Waterfall from investment to profitability

6. **Sensitivity**: What if price drops 10%? What if variable costs increase 20%? Model 2-3 scenarios.

7. **Save to wiki**: `wiki/synthesis/break-even-[project].md`

## Output format

```markdown
# Break-Even Analysis: [Product/Project]

## Cost Structure
| Cost type | Amount | Frequency |
|---|---|---|
| ... | €X | Monthly/One-time |

## Break-Even Point
- **Units**: X,XXX units
- **Revenue**: €X,XXX
- **Timeline**: Month X (at projected growth rate)

## Scenario Analysis
| Scenario | Break-even units | Break-even month |
|---|---|---|
| Base | X | Month Y |
| Price -10% | X | Month Y |
| Costs +20% | X | Month Y |

## Recommendation
[Go/No-go with reasoning]
```

## Pitfalls

- Don't forget opportunity cost — what else could the investment fund?
- Include all fixed costs, not just the obvious ones (overhead allocation)
- For SaaS: account for churn in the time-based model
- State the growth assumptions behind the timeline estimate
