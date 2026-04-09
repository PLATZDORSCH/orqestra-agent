---
title: "Business Model Canvas"
description: "Map a complete business model using the Business Model Canvas framework."
tags: [strategy, business-model, canvas, frameworks]
version: 1
created: "2026-04-08"
---

# Business Model Canvas

Map a complete business model on a single page using Alexander Osterwalder's framework.

## When to use

- User wants to design or evaluate a business model
- User says "business model canvas", "BMC", "map the business model"
- User is launching a new product/venture or pivoting

## Steps

1. **Gather context**: Use `kb_search` for existing knowledge about the business, market, competitors. Use `web_search` if needed.

2. **Fill out the 9 blocks** — in this order (right side = desirability, left side = feasibility, bottom = viability):

   **Right side (Customer):**
   - **Customer Segments**: Who are we creating value for? Be specific. Personas, not demographics.
   - **Value Propositions**: What value do we deliver? What problem do we solve? Why us vs. alternatives?
   - **Channels**: How do we reach customers? Sales, marketing, distribution.
   - **Customer Relationships**: What type? Self-service, personal, automated, community?
   - **Revenue Streams**: How does money flow in? Pricing model, willingness to pay.

   **Left side (Infrastructure):**
   - **Key Resources**: What do we need? People, IP, tech, brand, data.
   - **Key Activities**: What do we do? Development, marketing, operations.
   - **Key Partnerships**: Who helps us? Suppliers, platforms, strategic alliances.

   **Bottom:**
   - **Cost Structure**: What are the biggest costs? Fixed vs. variable. Cost-driven vs. value-driven?

3. **Visualize**: Create a formatted canvas layout or use markdown tables.

4. **Identify risks**: For each block, note the biggest assumption/risk.

5. **Save to wiki**: `wiki/synthesis/bmc-[business-name].md`

## Output format

```markdown
# Business Model Canvas: [Business Name]

## Customer Segments
- Segment 1: [Description, size, needs]
- Segment 2: ...

## Value Propositions
- For Segment 1: [Problem → Solution → Benefit]
- For Segment 2: ...

## Channels
| Stage | Channel |
|---|---|
| Awareness | ... |
| Evaluation | ... |
| Purchase | ... |
| Delivery | ... |
| After-sales | ... |

## Customer Relationships
- Segment 1: [Type and approach]

## Revenue Streams
| Stream | Model | Price range |
|---|---|---|
| ... | Subscription / Per-unit / ... | €X-Y |

## Key Resources
- [Resource]: [Why critical]

## Key Activities
- [Activity]: [Description]

## Key Partnerships
- [Partner]: [What they provide]

## Cost Structure
| Cost | Type | Estimate |
|---|---|---|
| ... | Fixed/Variable | €X/month |

## Key Risks & Assumptions
| Block | Assumption | Risk level |
|---|---|---|
| Value Prop | [Customers care about X] | High |
| Revenue | [WTP is €Y/month] | Medium |
```

## Pitfalls

- Don't describe what the company does — describe the business MODEL (how value is created, delivered, captured)
- Value proposition is not "our product" — it's the outcome the customer gets
- Revenue streams should include pricing logic, not just "we charge money"
- The canvas is a snapshot — date it and update when the model evolves
