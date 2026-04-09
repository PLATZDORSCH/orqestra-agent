---
title: "OKR / KPI Framework"
description: "Define Objectives and Key Results (OKRs) or KPIs for a team, product, or company."
tags: [strategy, okr, kpi, goals, measurement]
version: 1
created: "2026-04-08"
---

# OKR / KPI Framework

Define measurable goals that align teams and track progress.

## When to use

- User wants to set quarterly or annual goals
- User says "OKRs", "KPIs", "goals", "what should we measure?"
- User needs to align team efforts with business objectives

## Steps

1. **Clarify scope**: Company-level, team-level, or product-level? What time period (quarter/year)?

2. **Define 3-5 Objectives**: Each objective should be:
   - Qualitative and inspiring ("Become the go-to CRM for trades")
   - Ambitious but achievable
   - Time-bound (this quarter)
   - Aligned with company strategy

3. **Define 2-4 Key Results per Objective**: Each KR should be:
   - Quantitative and measurable
   - Outcome-based, not activity-based ("Reach 1000 MRR" not "Send 50 emails")
   - Has a clear target number
   - Achievable but stretchy (70% completion = success in OKR philosophy)

4. **Define tracking KPIs**: For ongoing monitoring beyond OKRs:
   - Leading indicators (predict future outcomes)
   - Lagging indicators (measure past outcomes)
   - Health metrics (ensure nothing breaks while pursuing OKRs)

5. **Alignment check**: Do team OKRs ladder up to company OKRs? Are there conflicts between teams?

6. **Create tracking dashboard spec**: What needs to be measured, data source, frequency.

7. **Save**: `wiki/synthesis/okr-YYYY-QX.md`

## Output format

```markdown
# OKRs: [Team/Company] — Q[X] [Year]

## Objective 1: [Inspiring qualitative goal]
- **KR 1.1**: [Metric] from [current] to [target]
- **KR 1.2**: [Metric] from [current] to [target]
- **KR 1.3**: [Metric] from [current] to [target]

## Objective 2: [Inspiring qualitative goal]
- **KR 2.1**: ...
- **KR 2.2**: ...

## Objective 3: [Inspiring qualitative goal]
- **KR 3.1**: ...
- **KR 3.2**: ...

## Health Metrics (Don't Let These Drop)
| Metric | Current | Minimum | Source |
|---|---|---|---|
| Churn rate | 3% | <5% | Billing system |
| NPS | 45 | >40 | Survey |
| ... | | | |

## KPI Dashboard
| KPI | Type | Frequency | Owner | Source |
|---|---|---|---|---|
| MRR | Lagging | Weekly | Finance | Stripe |
| Pipeline value | Leading | Weekly | Sales | CRM |
| ... | | | | |
```

## Pitfalls

- Don't set more than 5 objectives — focus is the point
- Key results must be measurable — "improve customer satisfaction" is not a KR
- Don't confuse activities with outcomes — "launch feature X" is a task, not a KR
- OKRs should be uncomfortable — if you hit 100% every time, you're not stretching enough
- Review weekly, not just at quarter-end
