---
title: "Risk Assessment"
description: "Identify, evaluate, and prioritize business risks with a risk matrix."
tags: [strategy, risk, assessment, planning, frameworks]
version: 1
created: "2026-04-08"
---

# Risk Assessment

Systematically identify and evaluate risks for a project, product, or business decision.

## When to use

- User is evaluating a major decision or investment
- User says "risk assessment", "what could go wrong?", "risk matrix"
- Before a product launch, market entry, or strategic pivot

## Steps

1. **Define scope**: What are we assessing? (project, product launch, market entry, partnership, etc.)

2. **Identify risks** across categories:
   - **Market**: Demand, competition, timing, market shifts
   - **Technical**: Feasibility, scalability, dependencies, security
   - **Financial**: Funding, cash flow, pricing, currency
   - **Operational**: Team, processes, suppliers, capacity
   - **Legal/Regulatory**: Compliance, IP, contracts, data privacy
   - **Reputational**: Brand, trust, PR, customer perception

3. **Assess each risk**:
   - **Likelihood**: Low (1) / Medium (2) / High (3)
   - **Impact**: Low (1) / Medium (2) / High (3)
   - **Risk score**: Likelihood × Impact

4. **Prioritize**: Sort by risk score. Focus mitigation on high-impact, high-likelihood risks.

5. **Define mitigation strategies**:
   - **Avoid**: Change plan to eliminate the risk
   - **Reduce**: Take action to lower likelihood or impact
   - **Transfer**: Insurance, contracts, partnerships
   - **Accept**: Monitor and prepare contingency

6. **Visualize**: Use `generate_chart` or `run_script` for a risk matrix (scatter plot: likelihood vs. impact).

7. **Save**: `wiki/synthesis/risk-assessment-[topic].md`

## Output format

```markdown
# Risk Assessment: [Topic]

## Risk Register

| # | Risk | Category | Likelihood | Impact | Score | Mitigation |
|---|---|---|---|---|---|---|
| 1 | [Description] | Market | High (3) | High (3) | 9 | [Strategy] |
| 2 | [Description] | Technical | Medium (2) | High (3) | 6 | [Strategy] |
| 3 | [Description] | Financial | Low (1) | High (3) | 3 | [Strategy] |
| ... | | | | | | |

## Top 3 Risks (Detailed)

### Risk 1: [Name]
- **Description**: ...
- **Trigger**: What would cause this?
- **Impact**: What happens if it materializes?
- **Mitigation**: [Specific actions]
- **Contingency**: [Plan B if it happens anyway]
- **Owner**: [Who monitors this?]

### Risk 2: [Name]
...

## Risk Matrix
[Chart: 3x3 grid with risks plotted by likelihood/impact]

## Monitoring Plan
| Risk | Indicator | Threshold | Check frequency |
|---|---|---|---|
| ... | ... | ... | Weekly/Monthly |

## Overall Assessment
[Go/No-go recommendation with reasoning]
```

## Pitfalls

- Don't stop at identification — every risk needs an owner and a mitigation plan
- Be honest about likelihood — optimism bias is the #1 risk assessment failure
- Include second-order effects — "supplier fails" → "delivery delayed" → "customer churns"
- Update the assessment when new information arrives — it's a living document
- Don't over-engineer low-score risks — focus energy on the top 5
