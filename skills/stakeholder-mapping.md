---
title: "Stakeholder Mapping"
description: "Map stakeholders by influence and interest to plan engagement strategy."
tags: [operations, stakeholder, planning, communication]
version: 1
created: "2026-04-08"
---

# Stakeholder Mapping

Identify and prioritize stakeholders for a project, product, or decision.

## When to use

- User is planning a project or initiative with multiple stakeholders
- User says "stakeholder mapping", "who do I need to involve?", "influence matrix"
- Before a major decision that affects multiple teams or external parties

## Steps

1. **List all stakeholders**: Brainstorm everyone affected by or influencing the initiative:
   - Internal: executives, teams, departments
   - External: customers, partners, investors, regulators, media

2. **Classify each stakeholder**:
   - **Influence**: High / Medium / Low (can they block or accelerate?)
   - **Interest**: High / Medium / Low (do they care about the outcome?)
   - **Attitude**: Supporter / Neutral / Skeptic / Opponent

3. **Map to quadrants** (Power/Interest Grid):
   | | High Interest | Low Interest |
   |---|---|---|
   | **High Influence** | Manage closely | Keep satisfied |
   | **Low Influence** | Keep informed | Monitor |

4. **Define engagement strategy per quadrant**:
   - **Manage closely**: Regular 1:1 updates, involve in decisions, seek input
   - **Keep satisfied**: Periodic updates, address concerns proactively
   - **Keep informed**: Newsletter, group updates, dashboards
   - **Monitor**: Minimal effort, react if their position changes

5. **Create communication plan**: Who gets what information, how often, via which channel.

6. **Save**: `wiki/synthesis/stakeholders-[project].md`

## Output format

```markdown
# Stakeholder Map: [Project/Initiative]

## Stakeholder Register
| Stakeholder | Role | Influence | Interest | Attitude | Strategy |
|---|---|---|---|---|---|
| [Name/Role] | Decision maker | High | High | Supporter | Manage closely |
| [Name/Role] | End user | Low | High | Neutral | Keep informed |
| ... | | | | | |

## Power/Interest Grid

### Manage Closely (High Influence + High Interest)
- [Stakeholder]: [Engagement approach]

### Keep Satisfied (High Influence + Low Interest)
- [Stakeholder]: [Engagement approach]

### Keep Informed (Low Influence + High Interest)
- [Stakeholder]: [Engagement approach]

### Monitor (Low Influence + Low Interest)
- [Stakeholder]: [Engagement approach]

## Communication Plan
| Stakeholder | Format | Frequency | Channel | Owner |
|---|---|---|---|---|
| ... | Status update | Weekly | Email | PM |
| ... | Executive brief | Monthly | Meeting | Director |
```

## Pitfalls

- Don't forget end users — they often have low power but high impact on adoption
- Skeptics aren't enemies — engage them early, their concerns often improve the plan
- Attitude can change — reassess after key milestones
- One-size-fits-all communication fails — tailor the message to each quadrant
