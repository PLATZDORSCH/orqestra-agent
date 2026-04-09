---
title: "Pricing Analysis"
description: "Analyze and recommend pricing strategy for a product or service."
tags: [strategy, pricing, revenue, competitive]
version: 1
created: "2026-04-08"
---

# Pricing Analysis

Evaluate current pricing or design a pricing strategy for a product/service.

## When to use

- User wants to set or change pricing
- User says "pricing strategy", "how much should we charge?", "pricing comparison"
- User is launching a new product and needs pricing guidance

## Steps

1. **Understand the product**: What's the value delivered? What's the business model (SaaS, transactional, usage-based, freemium)?

2. **Competitive pricing research**: Use `web_search` + `fetch_url` to map competitor pricing:
   - Fetch pricing pages of 5-10 competitors
   - Build a comparison matrix
   - Note: tiers, features per tier, discounts

3. **Value-based analysis**: What's the customer's willingness to pay?
   - What does the problem cost them today? (cost of status quo)
   - What's the ROI of your solution?
   - Price should be 10-20% of the value delivered

4. **Cost-plus floor**: Use `run_script` to calculate:
   - COGS per customer/unit
   - Minimum price for target gross margin
   - This is the floor, not the strategy

5. **Pricing model options**: Evaluate:
   | Model | Pros | Cons | Best for |
   |---|---|---|---|
   | Per-seat | Predictable, easy | Limits adoption | B2B SaaS |
   | Usage-based | Aligns with value | Revenue volatility | APIs, infra |
   | Tiered | Captures segments | Complexity | Most SaaS |
   | Freemium | Growth driver | Low conversion | PLG |
   | Flat rate | Simple | Leaves money on table | Simple products |

6. **Design tiers** (if applicable): Good/Better/Best with:
   - Entry tier: solves core problem, low barrier
   - Mid tier: most popular, best value (anchor)
   - Top tier: all features, enterprise needs, higher margin

7. **Visualize**: Use `generate_chart` for competitive positioning (scatter plot via run_script or bar chart).

8. **Save**: `wiki/synthesis/pricing-[product].md`

## Output format

```markdown
# Pricing Analysis: [Product]

## Competitive Landscape
| Competitor | Entry | Mid | Enterprise | Model |
|---|---|---|---|---|
| ... | €X | €Y | €Z | Per-seat |

## Value-Based Price Range
- Cost of problem: €X/month
- Our value delivered: €Y/month
- Recommended range: €A-B/month (10-20% of value)

## Recommended Pricing

### Starter — €X/month
- [Feature list]
- Target: [Segment]

### Professional — €Y/month (recommended)
- [Feature list]
- Target: [Segment]

### Enterprise — €Z/month
- [Feature list]
- Target: [Segment]

## Revenue Impact
[Projected revenue at different price points using run_script]

## Risks
- Too high: [consequence]
- Too low: [consequence]
```

## Pitfalls

- Don't price based on cost alone — price based on value
- Don't have too many tiers — 3 is the sweet spot
- The middle tier should be the obvious choice (anchoring effect)
- Annual pricing should offer 15-20% discount to improve cash flow
- Test pricing with real prospects before committing
